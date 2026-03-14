from datetime import datetime
from openpyxl import Workbook
from django.http import HttpResponse
from .filters import JobProcessFilter, JobFilter, JobMaterialFilter
from .models import JobProcess, Job, JobMaterial
from openpyxl.styles import Alignment


def joblist(request):

    q = request.GET.get('q', None)
    if q != None:
        print(q)
        job_list = Job.objects.filter(jobstatus=q)
    else:
        print(q)
        job_list = Job.objects.all()

    myFilter = JobFilter(request.GET, job_list)
    job_list = myFilter.qs
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename={date}-job.xlsx'.format(
        date=datetime.now().strftime('%Y-%m-%d'), )
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = 'Job'
    columns = ['id', 'Itemmaster', 'Quantity', 'Unit', 'Kg', 'Status', 'Size', 'Waste%']

    worksheet.column_dimensions['B'].width = 20
    row_num = 1
    for col_num, column_title in enumerate(columns, 1):
        cell = worksheet.cell(row=row_num, column=col_num)
        cell.value = column_title
    for job in job_list:
        row_num += 1
        row = [job.id, str(job.itemname), job.quantity, str(job.unit), job.kgqty, str(job.jobstatus),
               job.film_size, job.jobwaste]
        for col_num, cell_value in enumerate(row, 1):
            cell = worksheet.cell(row=row_num, column=col_num)
            cell.value = cell_value
    workbook.save(response)
    return response


def processlist(request, status=None):

    if status == 'All':
        proc_list = JobProcess.objects.all().order_by('-job__film_size')
    else:
        proc_list = JobProcess.objects.filter(process__process=status).order_by('-job__film_size')
    myFilter = JobProcessFilter(request.GET, proc_list)
    process_queryset = myFilter.qs
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename={date}-{status}.xlsx'.format(
        date=datetime.now().strftime('%Y-%m-%d'),status=status )
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = str(status)

    wrap_alignment = Alignment(wrap_text=True, vertical='top')

    # Apply to column dimensions
    worksheet.column_dimensions['A'].alignment = wrap_alignment

    columns = ['Job', 'Process', 'Qty', 'Unit','Pouch Type', 'Pouch Qty', 'Status', 'Size','Cylinder']
    col_width = {"A": 100, "B": 10, "C": 10, "D": 10, "E": 30, "F": 10, "G": 10, "H":10,"I":10}
    for col in col_width:
        worksheet.column_dimensions[col].width = col_width[col]


    row_num = 1

    for col_num, column_title in enumerate(columns, 1):
        cell = worksheet.cell(row=row_num, column=col_num)
        cell.value = column_title

    for process in process_queryset:
        row_num += 1
        if process.process.process =="Lamination":
            ply= " " + str(process.process_count + 1)+ "Ply"
        else:
            ply=""

        row = [str(process.job) + ply, str(process.process), process.qty, str(process.unit), str(process.job.pouch_type),process.job.totalpouch,
               str(process.status), process.job.film_size, process.job.itemmaster.cylinder_status]
        for col_num, cell_value in enumerate(row, 1):
            cell = worksheet.cell(row=row_num, column=col_num)
            cell.value = cell_value
            cell.alignment = wrap_alignment

    workbook.save(response)
    return response


def jobmaterialexcel(request):


    q = request.GET.get('q', None)
    if q != None:
        print(q)
        jobmaterial_list = JobMaterial.objects.select_related('materialname', 'item_mat_type',
                                                              'item_grade').filter(jobstatus=q)
    else:
        print(q)
        jobmaterial_list = JobMaterial.objects.select_related('materialname', 'item_mat_type',
                                                              'item_grade').all()

    myFilter = JobMaterialFilter(request.GET, jobmaterial_list)
    jobmaterial_list = myFilter.qs

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename={date}-job.xlsx'.format(
        date=datetime.now().strftime('%Y-%m-%d'), )
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = 'Requried Material'
    columns = ['Job', 'status', 'Material', 'Type', 'Grade', 'Size', 'Micron', 'Required',
               'Available', 'To Order', 'Ordered','Rec','opt1', 'opt2']
    row_num = 1
    for col_num, column_title in enumerate(columns, 1):
        cell = worksheet.cell(row=row_num, column=col_num)
        cell.value = column_title
    for mate in jobmaterial_list:
        row_num += 1
        row = [str(mate.job), str(mate.job.jobstatus), str(mate.materialname), str(mate.item_mat_type),
               str(mate.item_grade), mate.size, mate.micron, mate.required, mate.avail,
               mate.to_order, mate.orderedqty, mate.receivedqty]

        for col_num, cell_value in enumerate(row, 1):
            cell = worksheet.cell(row=row_num, column=col_num)
            cell.value = cell_value
    workbook.save(response)
    return response
