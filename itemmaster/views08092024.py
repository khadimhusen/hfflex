from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.forms import modelformset_factory, inlineformset_factory
from .models import ItemMaster, RawMaterial, ItemImage, ItemProcess, ItemColor, ItemAttribute
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import login_required
from .forms import ItemMasterForm, RawMaterialForm, ItemProcessForm, ItemColorForm
from myproject.access import accessview
from .filters import ItemmasterFilter


@login_required(login_url='/login/')
@accessview
def itemlist(request):
    q = request.GET.get('q', None)
    if q != None:
        item_list = ItemMaster.objects.select_related('itemcustomer').filter(active=q)
    else:
        item_list = ItemMaster.objects.select_related('itemcustomer').all()

    myFilter = ItemmasterFilter(request.GET, item_list)
    item_list = myFilter.qs
    totalcount = item_list.count()

    page = request.GET.get('page', 1)
    paginator = Paginator(item_list, 100)

    try:
        items = paginator.page(page)
    except PageNotAnInteger:
        items = paginator.page(1)
    except EmptyPage:
        items = paginator.page(paginator.num_pages)
    return render(request, 'itemmaster/itemlist.html',
                  {'items': items, 'q': q, 'total': totalcount, 'myFilter': myFilter})


@login_required(login_url='/login/')
@accessview
def itemdetail(request, id):
    context = {}
    itemmaster = get_object_or_404(ItemMaster, id=id)
    rawmaterialformset = inlineformset_factory(ItemMaster, RawMaterial, form=RawMaterialForm, extra=0)
    item_form = ItemMasterForm(instance=itemmaster)
    formset2 = rawmaterialformset(instance=itemmaster, prefix='rawmaterialformset')
    context['item_form'] = item_form
    context['rawmaterial_forms'] = formset2
    context['item'] = itemmaster.itemimage.all()
    context['itemply'] = itemmaster
    return render(request, 'itemmaster/itemdetail.html', context)


@login_required(login_url='/login/')
@accessview
def cylinderdetail(request, id):
    itemmaster = get_object_or_404(ItemMaster, id=id)
    nextitem= id+1
    previousitem= id-1
    print("next:", nextitem, previousitem)
    context = {'itemmaster': itemmaster,'nextid':nextitem, 'previousid':previousitem}
    return render(request, 'itemmaster/Cylinderdetail.html',context)


@login_required(login_url='/login/')
@accessview
def itemadd(request):
    context = {}
    if request.method == 'POST':
        item_form = ItemMasterForm(request.POST)
        context['item_form'] = item_form
        if item_form.is_valid():
            item = item_form.save(commit=False)
            item.createdby = request.user
            item.save()
            messages.success(request, "Itemmaster Created Successfully, Please Add Other Detail")
            return HttpResponseRedirect(reverse('itemmaster:itemdetailedit', kwargs={'id': item.id}))
        else:
            return render(request, 'itemmaster/add.html', context)
    else:
        item_form = ItemMasterForm()
        context['item_form'] = item_form
        return render(request, 'itemmaster/add.html', context)


@login_required(login_url='/login/')
@accessview
def itemclone(request, id=None):
    itemmaster = get_object_or_404(ItemMaster, id=id)
    context = {}
    if request.method == 'POST':
        item_form = ItemMasterForm(request.POST)
        context['item_form'] = item_form
        if item_form.is_valid():
            item = item_form.save(commit=False)
            item.createdby = request.user
            item.save()
            messages.success(request, "Itemmaster Created Successfully, Please Add Other Detail")
            return HttpResponseRedirect(reverse('itemmaster:itemdetailedit', kwargs={'id': item.id}))
        else:

            messages.success(request, item_form.errors)
            return render(request, 'itemmaster/add.html', context)
    else:
        item_form = ItemMasterForm(instance=itemmaster)
        context['item_form'] = item_form

        return render(request, 'itemmaster/add.html', context)


@login_required(login_url='/login/')
@accessview
def itemmasterdetailadd(request):
    context = {}
    imageformset = modelformset_factory(ItemImage, fields=('imagename',), extra=2)
    rawmaterialformset = modelformset_factory(RawMaterial, form=RawMaterialForm, extra=3)
    if request.method == 'POST':
        item_form = ItemMasterForm(request.POST)
        formset1 = imageformset(request.POST or None, request.FILES, prefix='imageformeset')
        formset2 = rawmaterialformset(request.POST or None, prefix='rawmaterialformeset')
        context['item_form'] = item_form
        context['image_forms'] = formset1
        context['rawmaterial_forms'] = formset2

        if item_form.is_valid() and formset1.is_valid() and formset2.is_valid():
            item = item_form.save()
            for f1 in formset1:
                print(f1.cleaned_data)
                if f1.cleaned_data:
                    if f1.cleaned_data['id'] is None:
                        image = f1.save(commit=False)
                        image.itemname = item
                        image.save()
            for f2 in formset2:

                if f2.cleaned_data:
                    if f2.cleaned_data['id'] is None:
                        rawmaterial = f2.save(commit=False)
                        rawmaterial.itemmaster = item
                        rawmaterial.save()
            return HttpResponseRedirect(reverse('itemmaster:itemlist'))
        else:
            return render(request, 'itemmaster/new_itemmaster.html', context)
    else:
        item_form = ItemMasterForm()
        context['item_form'] = item_form
        context['image_forms'] = imageformset(queryset=ItemImage.objects.none(), prefix='imageformeset')
        context['rawmaterial_forms'] = rawmaterialformset(queryset=RawMaterial.objects.none(),
                                                          prefix='rawmaterialformeset')
        return render(request, 'itemmaster/new_itemmaster.html', context)


@login_required(login_url='/login/')
@accessview
def itemmasterdetailedit(request, id=None):
    context = {}
    itemmaster = get_object_or_404(ItemMaster, id=id)
    context['itemmaster'] = itemmaster
    imageformset = inlineformset_factory(ItemMaster, ItemImage, fields=('imagename',), extra=2, max_num=6)
    rawmaterialformset = inlineformset_factory(ItemMaster, RawMaterial, form=RawMaterialForm, extra=6, max_num=8)
    itemprocessformset = inlineformset_factory(ItemMaster, ItemProcess, form=ItemProcessForm, extra=8, max_num=8)
    itemcolorformset = inlineformset_factory(ItemMaster, ItemColor, form=ItemColorForm, extra=8, max_num=8)
    itemattributeformset = inlineformset_factory(ItemMaster, ItemAttribute, fields=('item_attirbuate', 'attri_value'),
                                                 extra=8, max_num=12)

    if request.method == 'POST':
        item = ItemMasterForm(request.POST, instance=itemmaster)
        formset1 = imageformset(request.POST, request.FILES, prefix='imageformset', instance=itemmaster)
        formset2 = rawmaterialformset(request.POST, prefix='rawmaterialformset', instance=itemmaster)
        formset3 = itemprocessformset(request.POST, prefix='processformset', instance=itemmaster)
        formset4 = itemcolorformset(request.POST, prefix='colorformset', instance=itemmaster)
        formset5 = itemattributeformset(request.POST, prefix='attributeformset', instance=itemmaster)

        context['item_form'] = item
        context['image_forms'] = formset1
        context['rawmaterial_forms'] = formset2
        context['process_forms'] = formset3
        context['color_forms'] = formset4
        context['attribute_forms'] = formset5
        if (item.is_valid() and formset1.is_valid()
                and formset2.is_valid() and formset3.is_valid()
                and formset4.is_valid() and formset5.is_valid()):

            item.save(commit=False)
            item.editedby = request.user
            item.save()
            formset1.save()
            formset2.save()
            formset3.save()
            formset4.save()
            formset5.save()
            return HttpResponseRedirect(reverse('itemmaster:itemlist'))
        else:
            print("item erro", item.errors)
            print("formset errror1", formset1.errors)
            print("formset errror2", formset2.errors)
            print("formset errror3", formset3.errors)
            print("formset errror4", formset4.errors)
            print("formset errror5", formset5.errors)
            context['something'] = "something"
            return render(request, 'itemmaster/edit_itemmaster.html', context)
    else:
        if request.user == itemmaster.createdby or request.user.username == "admin" or request.user.username == 'khadimhusen':
            item = ItemMasterForm(instance=itemmaster)
            formset1 = imageformset(instance=itemmaster, prefix='imageformset')
            formset2 = rawmaterialformset(instance=itemmaster, prefix='rawmaterialformset')
            formset3 = itemprocessformset(instance=itemmaster, prefix='processformset')
            formset5 = itemattributeformset(prefix='attributeformset', instance=itemmaster)
            formset4 = itemcolorformset(prefix='colorformset', instance=itemmaster)
            context['item_form'] = item
            context['image_forms'] = formset1
            context['rawmaterial_forms'] = formset2
            context['process_forms'] = formset3
            context['color_forms'] = formset4
            context['attribute_forms'] = formset5
            return render(request, 'itemmaster/edit_itemmaster.html', context)
        else:
            messages.success(request,
                             f'You are not Authorise to change detail of this Itemmaster only {itemmaster.createdby} can change. ')
            return HttpResponseRedirect(reverse('itemmaster:itemlist'))


@login_required(login_url='/login/')
@accessview
def deepitemclone(request, id=None):
    itemmaster = get_object_or_404(ItemMaster, id=id)
    context = {}
    if request.method == 'POST':
        item_form = ItemMasterForm(request.POST)
        context['item_form'] = item_form
        if item_form.is_valid():
            item = item_form.save(commit=False)
            item.createdby = request.user
            item.save()
            rawmateriallist = itemmaster.rawmaterial.all()
            for i in rawmateriallist:
                RawMaterial.objects.create(
                    itemmaster=item,
                    materialname=i.materialname,
                    item_mat_type=i.item_mat_type,
                    item_grade=i.item_grade,
                    size=i.size,
                    micron=i.micron,
                    gsm=i.gsm,
                    createdby=request.user
                )
            processlist = itemmaster.itemprocess.all()
            for i in processlist:
                ItemProcess.objects.create(
                    itemmaster=item,
                    process=i.process,
                    unit=i.unit,
                    machine=i.machine,
                    createdby=request.user
                )
            itemcolorlist = itemmaster.itemcolors.all()
            for i in itemcolorlist:
                ItemColor.objects.create(
                    itemmaster=item,
                    color=i.color,
                    remark=i.remark
                )
            itemattributelist = itemmaster.itemattribute.all()
            for i in itemattributelist:
                ItemAttribute.objects.create(
                    item_attirbuate=i.item_attirbuate,
                    itemmaster=item,
                    attri_value=i.attri_value
                )

            messages.success(request, "Itemmaster Created Successfully, Please Add Other Detail")
            return HttpResponseRedirect(reverse('itemmaster:itemdetailedit', kwargs={'id': item.id}))
        else:

            messages.success(request, item_form.errors)
            return render(request, 'itemmaster/add.html', context)
    else:
        item_form = ItemMasterForm(instance=itemmaster)
        context['item_form'] = item_form
        return render(request, 'itemmaster/add.html', context)
