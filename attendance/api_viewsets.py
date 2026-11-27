import csv
import io
import re
from datetime import date as date_type, datetime, time, timedelta

from django.db.models import Q
from django.http import HttpResponse
from rest_framework import mixins, status as http, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from employee.models import Worker

from . import services, shifts
from .api_serializers import (
    AttendanceDaySerializer, DayWriteSerializer, PunchCreateSerializer, PunchLogSerializer, hours_text,
)
from .exports import excel_filename, generate_month_xlsx
from .filters import DayFilter, PunchFilter
from .models import AttendanceDay, PunchLog, ShiftAssignment
from .permissions import IsAttendanceUser

XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_ROWS = 50000


def _date_param(request, name='date'):
    value = request.query_params.get(name) or request.data.get(name)
    try:
        return datetime.strptime(str(value), '%Y-%m-%d').date()
    except ValueError:
        raise ValidationError({name: 'Give the date as YYYY-MM-DD.'})


def _month_param(request):
    value = request.query_params.get('month') or ''
    match = re.fullmatch(r'(\d{4})-(\d{1,2})', value)
    if not match or not 1 <= int(match.group(2)) <= 12:
        raise ValidationError({'month': 'Give the month as YYYY-MM.'})
    return int(match.group(1)), int(match.group(2))


def _convert(error):
    return ValidationError({'detail': str(error)})


class PunchLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                      mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """The raw punches. Entered by hand, imported, or (later) synced from eTimeOffice."""
    permission_classes = [IsAttendanceUser]
    queryset = PunchLog.objects.select_related('worker', 'created_by')
    serializer_class = PunchLogSerializer
    filterset_class = PunchFilter

    def create(self, request, *args, **kwargs):
        form = PunchCreateSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        worker, when = form.validated_data['worker'], form.validated_data['punched_at'].replace(tzinfo=None, microsecond=0)
        code = services.clean_code(worker.emp_code) or f'W{worker.pk}'
        if PunchLog.objects.filter(emp_code=code, punched_at=when).exists():
            raise ValidationError({'punched_at': 'This punch is already recorded.'})
        punch = PunchLog.objects.create(worker=worker, emp_code=code, punched_at=when, source='manual',
                                        note=form.validated_data['note'], created_by=request.user)
        services.rebuild_days(worker, when.date() - timedelta(days=1), when.date())
        return Response(PunchLogSerializer(punch).data, status=http.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        worker, day = instance.worker, instance.punched_at.date()
        instance.delete()
        if worker is not None:
            services.rebuild_days(worker, day - timedelta(days=1), day)

    @action(detail=False, methods=['post'])
    def bulk(self, request):
        """{"source": "etimeoffice", "rows": [{"emp_code": "37", "punched_at": "2026-11-20T08:01:00"}, ...]}"""
        rows = request.data.get('rows')
        if not isinstance(rows, list) or not rows:
            raise ValidationError({'rows': 'Send a list of punches.'})
        if len(rows) > MAX_ROWS:
            raise ValidationError({'rows': f'At most {MAX_ROWS} punches at a time.'})
        source = request.data.get('source') or 'file'
        if source not in dict(PunchLog.SOURCES):
            raise ValidationError({'source': 'Unknown source.'})
        return Response(services.record_punches(rows, source=source, user=request.user))

    @action(detail=False, methods=['post'], url_path='import-csv')
    def import_csv(self, request):
        """A CSV with a code column (emp_code, Empcode, code or id) and either one date-and-time
        column (punched_at, PunchDate, datetime) or separate date and time columns."""
        upload = request.FILES.get('file')
        if upload is None:
            raise ValidationError({'file': 'Choose a CSV file.'})
        if upload.size > MAX_UPLOAD_BYTES:
            raise ValidationError({'file': 'The file is larger than 5 MB.'})
        try:
            text = upload.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            raise ValidationError({'file': 'The file is not a text CSV (save it as CSV UTF-8).'})
        reader = csv.DictReader(io.StringIO(text))
        key = lambda name: re.sub(r'[^a-z]', '', (name or '').lower())
        rows = []
        for line in reader:
            cells = {key(k): (v or '').strip() for k, v in line.items() if k}
            code = next((cells[k] for k in ('empcode', 'code', 'id', 'employeecode') if cells.get(k)), '')
            when = next((cells[k] for k in ('punchedat', 'punchdate', 'datetime', 'punchtime') if cells.get(k)), '')
            if not when and cells.get('date'):
                when = f"{cells['date']} {cells.get('time', '')}".strip()
            rows.append({'emp_code': code, 'punched_at': when, 'device': cells.get('device') or cells.get('mcid', '')})
            if len(rows) > MAX_ROWS:
                raise ValidationError({'file': f'At most {MAX_ROWS} rows.'})
        if not rows:
            raise ValidationError({'file': 'The file has no rows.'})
        return Response(services.record_punches(rows, source='file', user=request.user))

    @action(detail=False, methods=['get'])
    def unmatched(self, request):
        """Codes that punched but are nobody's yet."""
        return Response(services.unmatched_codes())

    @action(detail=False, methods=['post'])
    def relink(self, request):
        return Response(services.relink_punches())


class AttendanceDayViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                           mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """One row per worker per day. Creating or changing one is a person's decision (it stays);
    deleting one hands the day back to the punches."""
    permission_classes = [IsAttendanceUser]
    queryset = AttendanceDay.objects.select_related('worker', 'edited_by')
    serializer_class = AttendanceDaySerializer
    filterset_class = DayFilter
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def _save(self, request, data):
        form = DayWriteSerializer(data=data)
        form.is_valid(raise_exception=True)
        values = form.validated_data
        strip = lambda v: v.replace(tzinfo=None, microsecond=0) if v else None
        try:
            return services.set_day(values['worker'], values['date'], values['status'], request.user,
                                    in_time=strip(values['in_time']), out_time=strip(values['out_time']),
                                    shift=values['shift'], remarks=values['remarks'])
        except services.AttendanceError as error:
            raise _convert(error)

    def create(self, request, *args, **kwargs):
        row = self._save(request, request.data)
        return Response(AttendanceDaySerializer(row).data, status=http.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        row = self.get_object()
        current = {'worker': row.worker_id, 'date': row.date, 'status': row.status, 'shift': row.shift,
                   'in_time': row.in_time, 'out_time': row.out_time, 'remarks': row.remarks}
        incoming = request.data.dict() if hasattr(request.data, 'dict') else dict(request.data)
        row = self._save(request, {**current, **incoming})
        return Response(AttendanceDaySerializer(row).data)

    def update(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        services.clear_manual(instance)

    @action(detail=False, methods=['get'])
    def roster(self, request):
        """Everyone who should be at work on a date, with their row (or none yet)."""
        day = _date_param(request)
        rows = services.roster(day)
        counts = {'not_marked': 0}
        entries = []
        for worker, row in rows:
            if row is None:
                counts['not_marked'] += 1
            else:
                counts[row.status] = counts.get(row.status, 0) + 1
            entries.append({'worker': worker.pk, 'worker_name': worker.worker_name, 'emp_code': worker.emp_code or '',
                            'day': AttendanceDaySerializer(row).data if row else None})
        return Response({'date': day.isoformat(), 'total': len(rows), 'counts': counts, 'rows': entries})

    @action(detail=False, methods=['post'], url_path='mark-absent')
    def mark_absent(self, request):
        day = _date_param(request)
        if day > date_type.today():
            raise ValidationError({'date': 'That day has not happened yet.'})
        return Response({'marked_absent': services.mark_absent(day, request.user)})

    @action(detail=False, methods=['post'])
    def rebuild(self, request):
        """Work the days out again from the punches (after a rule change or a late import)."""
        start, end = _date_param(request, 'date_from'), _date_param(request, 'date_to')
        if end < start or (end - start).days > 92:
            raise ValidationError({'date_to': 'Give a range of up to three months.'})
        return Response({'rows_changed': services.rebuild_range(start, end)})

    def _month_rows(self, request):
        year, month = _month_param(request)
        return year, month, services.month_sheet(year, month)

    @action(detail=False, methods=['get'])
    def month(self, request):
        """The month grid: a status for every worker and day, and each worker's totals."""
        year, month, sheet = self._month_rows(request)
        first, last = services.month_range(year, month)
        return Response({
            'month': f'{year}-{month:02d}', 'days_in_month': last.day,
            'rows': [{
                'worker': entry['worker'].pk, 'worker_name': entry['worker'].worker_name,
                'emp_code': entry['worker'].emp_code or '',
                'days': {str(d): {'id': r.id, 'status': r.status, 'worked_minutes': r.worked_minutes,
                                  'is_manual': r.is_manual} for d, r in entry['days'].items()},
                'counts': entry['counts'], 'worked_text': hours_text(entry['worked_minutes']),
                'overtime_text': hours_text(entry['overtime_minutes']), 'paid_days': entry['paid_days'],
            } for entry in sheet],
        })

    @action(detail=False, methods=['get'])
    def people(self, request):
        """Who can be looked up person by person: everyone active, and anyone who has days on record
        (so a worker who has left can still be opened for a past month)."""
        workers = Worker.objects.filter(Q(is_active=True) | Q(attendance_days__isnull=False)).distinct()             .order_by('worker_name')
        return Response([{'id': w.pk, 'name': w.worker_name, 'emp_code': w.emp_code or '', 'is_active': w.is_active,
                          'default_shift': w.default_shift} for w in workers])

    @action(detail=False, methods=['get'], url_path='shifts-on')
    def shifts_on(self, request):
        """The shift of everyone employed on a day: ?date=YYYY-MM-DD, and why (see services.shifts_on)."""
        day = _date_param(request)
        rows = []
        for r in services.shifts_on(day):
            entry = r['entry']
            rows.append({'worker': r['worker'].pk, 'worker_name': r['worker'].worker_name,
                         'emp_code': r['worker'].emp_code or '', 'shift': r['shift'], 'source': r['source'],
                         'usual': r['usual'],
                         'entry': {'id': entry.pk, 'from_date': entry.from_date.isoformat(),
                                   'to_date': entry.to_date.isoformat()} if entry else None})
        return Response({'date': day.isoformat(), 'rows': rows})

    @action(detail=False, methods=['get'], url_path='shift-ranges')
    def shift_ranges(self, request):
        """The date ranges shifts were given for, newest first: optionally ?worker=<id>."""
        entries = ShiftAssignment.objects.select_related('worker')
        if request.query_params.get('worker'):
            entries = entries.filter(worker_id=request.query_params['worker'])
        return Response([{'id': e.pk, 'worker': e.worker_id, 'worker_name': e.worker.worker_name,
                          'emp_code': e.worker.emp_code or '', 'from_date': e.from_date.isoformat(),
                          'to_date': e.to_date.isoformat(), 'shift': e.shift} for e in entries[:500]])

    @staticmethod
    def _assign_workers(request):
        ids = request.data.get('workers')
        if not isinstance(ids, list) or not ids:
            raise ValidationError({'workers': 'Choose at least one worker.'})
        try:
            workers = list(Worker.objects.filter(pk__in=[int(i) for i in ids]))
        except (TypeError, ValueError):
            raise ValidationError({'workers': 'Choose workers from the list.'})
        if len(workers) != len({int(i) for i in ids}):
            raise ValidationError({'workers': 'One of those workers does not exist.'})
        return workers

    @action(detail=False, methods=['post'], url_path='shift-overlaps')
    def shift_overlaps(self, request):
        """Before giving a shift: which entries of those workers it would replace or cut back
        ({workers, from_date, to_date}), and what each would keep."""
        workers = self._assign_workers(request)
        try:
            found = services.shift_conflicts(workers, _date_param(request, 'from_date'), _date_param(request, 'to_date'))
        except services.AttendanceError as error:
            raise ValidationError({'detail': str(error)})
        return Response({'overlaps': [{
            'id': c['entry'].pk, 'worker': c['entry'].worker_id, 'worker_name': c['entry'].worker.worker_name,
            'emp_code': c['entry'].worker.emp_code or '', 'from_date': c['entry'].from_date.isoformat(),
            'to_date': c['entry'].to_date.isoformat(), 'shift': c['entry'].shift,
            'kept': [{'from_date': a.isoformat(), 'to_date': b.isoformat()} for a, b in c['kept']],
        } for c in found]})

    @action(detail=False, methods=['post'], url_path='assign-shift')
    def assign_shift(self, request):
        """Give workers a shift from one date to another: {workers: [ids], from_date, to_date, shift}."""
        workers = self._assign_workers(request)
        try:
            changed = services.assign_shift(workers, _date_param(request, 'from_date'), _date_param(request, 'to_date'),
                                            request.data.get('shift') or '', request.user)
        except services.AttendanceError as error:
            raise ValidationError({'detail': str(error)})
        return Response({'assigned': len(workers), 'rows_changed': changed})

    @action(detail=False, methods=['post'], url_path='remove-shift-range')
    def remove_shift_range(self, request):
        """Take one entry away: {id}. Its days fall back to the entry before them."""
        try:
            entry = ShiftAssignment.objects.select_related('worker').get(pk=int(request.data.get('id', '')))
        except (ValueError, TypeError, ShiftAssignment.DoesNotExist):
            raise ValidationError({'id': 'That entry does not exist.'})
        return Response({'rows_changed': services.remove_assignment(entry)})

    @action(detail=False, methods=['post'], url_path='set-shift')
    def set_shift(self, request):
        """Set the shift a worker normally works (blank clears it) and work this month's days out again
        with it. Days of earlier months, and days corrected by hand, are left as they are."""
        try:
            worker = Worker.objects.get(pk=int(request.data.get('worker', '')))
        except (ValueError, TypeError, Worker.DoesNotExist):
            raise ValidationError({'worker': 'Choose a worker.'})
        shift = request.data.get('shift') or ''
        if shift and shift not in shifts.BY_KEY:
            raise ValidationError({'shift': 'Choose one of the shifts.'})
        worker.default_shift = shift
        worker.save(update_fields=['default_shift'])
        today = date_type.today()
        changed = services.rebuild_days(worker, today.replace(day=1), today)
        return Response({'worker': worker.pk, 'default_shift': worker.default_shift, 'rows_changed': changed})

    @action(detail=False, methods=['get'])
    def person(self, request):
        """One worker's month, every day of it, with the totals: ?worker=<id>&month=YYYY-MM."""
        try:
            worker = Worker.objects.get(pk=int(request.query_params.get('worker', '')))
        except (ValueError, Worker.DoesNotExist):
            raise ValidationError({'worker': 'Choose a worker.'})
        year, month = _month_param(request)
        data = services.person_month(worker, year, month)
        return Response({
            'worker': {'id': worker.pk, 'name': worker.worker_name, 'emp_code': worker.emp_code or '',
                       'is_active': worker.is_active, 'default_shift': worker.default_shift},
            'month': f'{year}-{month:02d}',
            'counts': data['counts'], 'not_marked': data['not_marked'], 'paid_days': data['paid_days'],
            'worked_text': hours_text(data['worked_minutes']), 'overtime_text': hours_text(data['overtime_minutes']),
            'days': [{'date': d['date'].isoformat(), 'weekday': d['date'].strftime('%a'), 'employed': d['employed'],
                      'holiday': d['holiday'], 'day': AttendanceDaySerializer(d['row']).data if d['row'] else None,
                      'punches': [{'id': p.pk, 'punched_at': p.punched_at.isoformat(), 'source': p.source,
                                   'device': p.device, 'note': p.note} for p in d['punches']]}
                     for d in data['days']],
        })

    @action(detail=False, methods=['get'], url_path='month-excel')
    def month_excel(self, request):
        year, month, sheet = self._month_rows(request)
        response = HttpResponse(content_type=XLSX)
        response['Content-Disposition'] = f'attachment; filename="{excel_filename(year, month)}"'
        generate_month_xlsx(response, year, month, sheet)
        return response
