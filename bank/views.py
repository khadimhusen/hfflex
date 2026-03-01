from django.contrib import messages
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Sum
from django.shortcuts import render, get_object_or_404, redirect


from bank.filters import ChequeFilter
from bank.forms import ChequeCreationForm, ChequeEditForm
from bank.models import Cheque, Bank
from customer.models import Customer
from myproject.access import accessview
from django.contrib.auth.decorators import login_required


@login_required(login_url='/login/')
@accessview
def chequelist(request):
    q = request.GET.get('q', None)
    if q is not None:
        cheque_list = Cheque.objects.filter(status=q)
    else:
        cheque_list = Cheque.objects.all()

    myFilter = ChequeFilter(request.GET, cheque_list)
    cheque_list = myFilter.qs
    totalcount = cheque_list.count()
    totalamount = cheque_list.aggregate(Sum('amount'))
    page = request.GET.get('page', 1)
    paginator = Paginator(cheque_list, 100)

    try:
        cheques = paginator.page(page)
    except PageNotAnInteger:
        cheques = paginator.page(1)
    except EmptyPage:
        cheques = paginator.page(paginator.num_pages)

    return render(request, 'Cheque/chequelist.html',
                  {'cheques': cheques, 'q': q, 'total': totalcount,
                   "totalamount": totalamount, 'myFilter': myFilter})


@login_required(login_url='/login/')
@accessview
def chequeadd(request):
    user = request.user
    if request.method == "POST":
        chequeform = ChequeCreationForm(request.POST)
        if chequeform.is_valid():
            bank = chequeform.cleaned_data["bank"]
            startnum = chequeform.cleaned_data["startnum"]
            endnum = chequeform.cleaned_data["endnum"]
            for num in range(startnum, endnum + 1):
                try:
                    Cheque.objects.create(bank=bank, number=num, createdby=user)
                except:
                    print()
            messages.warning(request, f'cheque created from {startnum} to {endnum}')

            return redirect("bank:chequelist")
        else:
            messages.warning(request, "Invalid Field")
            return render(request, 'Cheque/createcheque.html', {'chequeform': chequeform})
    else:
        chequeform = ChequeCreationForm()
        return render(request, 'Cheque/createcheque.html', {'chequeform': chequeform})


@login_required(login_url='/login/')
@accessview
def chequeedit(request, id=None):
    q = request.GET.get('q', "")

    context = {}
    context["q"]=q
    cheque = get_object_or_404(Cheque, id=id)
    partyname = list(Customer.objects.filter(is_supplier=True).values_list('name', flat=True))
    chequename = list(Cheque.objects.all().values_list('party', flat=True))
    context['partylist'] = sorted(set(list(filter(None, partyname)) + (list(filter(None, chequename)))))
    mainform = ChequeEditForm(request.POST or None, instance=cheque)
    context["mainform"] = mainform
    if request.method == 'POST':
        if mainform.is_valid():
            a = mainform.save(commit=False)
            a.editedby = request.user
            a.save()
            messages.warning(request, "cheque detail saved succesefylly")
            return redirect(f"/bank/list/?q={q}")
        else:
            messages.warning(request, "something wrong")
            mainform = ChequeEditForm(request.POST or None, instance=cheque)
            context["mainform"] = mainform
            return render(request, "Cheque/chequeedit.html", context)

    else:

        return render(request, "Cheque/chequeedit.html", context)



# def importdata():
#
#     f = open('bank/Book1.csv', 'r')
#     for line in f:
#         line = line.split(',')
#         bank=get_object_or_404(Bank,id=line[0])
#         cheque=line[1]
#         party=line[2]
#         chequedate=line[3]
#         amount=line[4]
#         remark=line[5]
#         status=line[6]
#         expected=line[3]
#         bill=line[8]
#         billdate=line[10]
#
#         obj, created = Cheque.objects.update_or_create(
#             number=cheque,
#             defaults={'bank': bank,
#                       "number":cheque,
#                       "party":party,
#                       "cheque_date":chequedate,
#                       "amount":amount,
#                       "remark":remark,
#                       "status":status,
#                       "expected_date":expected,
#                       "bill_number":bill,
#                       "bill_date":billdate
#                       })
#     f.close()
#
#
# def importdata2():
#     f = open('bank/Book3.csv', 'r')
#     for line in f:
#         line = line.split(',')
#         bank = get_object_or_404(Bank, id=line[0])
#         cheque = line[1]
#         party = line[2]
#         amount = line[3] or 0
#         remark = line[4]
#         status = line[5]
#
#         obj, created = Cheque.objects.update_or_create(
#             number=cheque,
#             defaults={'bank': bank,
#                       "number": cheque,
#                       "party": party,
#                       "amount": amount,
#                       "remark": remark,
#                       "status": status
#                       })
#     f.close()