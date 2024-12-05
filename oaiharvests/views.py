from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse, reverse_lazy
from django.utils import timezone, dateparse

from django import forms

from django.views.generic.base import TemplateView
from django.views.generic.list import ListView
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, UpdateView, DeleteView, FormView

from django.contrib import messages
import json

from oaipmh.client import Client
from oaipmh.metadata import MetadataRegistry, oai_dc_reader

from .models import Repository, Community, Collection, MetadataElement, Record
from .forms import CreateRepositoryForm, CreateCommunityForm, CreateCollectionForm
from .utils import OAIUtils, get_bitstream_url, filter_existing_collections, batch_harvest_issues, batch_harvest_articles

class OaiRepositoryListView(ListView):
    model = Repository
    template_name = 'oai_repository_list.html'


class OaiRepositoryView(DetailView):
    model = Repository
    template_name = 'oai_repository_detail.html'

    def get_context_data(self, **kwargs):
        context = super(OaiRepositoryView, self).get_context_data(**kwargs)
        obj = self.get_object()
        context['communities'] = obj.list_communities()
        return context


class OaiRepositoryCreateView(CreateView):
    model = Repository
    template_name = 'oai_repository_form.html'
    form_class = CreateRepositoryForm

    def get_context_data(self, **kwargs):
        context = super(OaiRepositoryCreateView, self).get_context_data(**kwargs)
        context['view_type'] = 'add'
        return context


class OaiRepositoryUpdateView(UpdateView):
    model = Repository
    template_name = 'oai_repository_form.html'
    fields = ['name']

    def get_context_data(self, **kwargs):
        context = super(OaiRepositoryUpdateView, self).get_context_data(**kwargs)
        context['view_type'] = 'update'
        return context


class OaiRepositoryDeleteView(DeleteView):
    model = Repository
    template_name = 'oai_confirm_delete.html'
    success_url = reverse_lazy('oai_repository_list')


class OaiCommunityView(DetailView):
    model = Community
    template_name = 'oai_community_detail.html'

    def get_context_data(self, **kwargs):
        context = super(OaiCommunityView, self).get_context_data(**kwargs)
        context['collections'] = self.get_object().list_collections()
        return context


class OaiCommunityCreateView(DetailView):
    model = Repository
    template_name = 'oai_community_add_form.html'
    oai = OAIUtils()

    def post(self, request, **kwargs):
        form = CreateCommunityForm(request.POST, repo=self.get_object(), community_list=self.oai.communities)

        if form.is_valid():
            choices = form.fields['identifier'].widget.choices
            for i in choices:
                if i[0] == form.instance.identifier:
                    form.instance.name = i[1]
                    break

            form.save()
            return HttpResponseRedirect(reverse('oai_repository', args=[str(self.get_object().id)]))

        return render('oai_community_add_form.html', {'form': form})
        

    def get_context_data(self, **kwargs):
        context = super(OaiCommunityCreateView, self).get_context_data(**kwargs)
        self.oai.list_oai_community_sets(self.get_object())
        
        form = CreateCommunityForm(repo=self.get_object(), community_list=self.oai.communities)
        context['form'] = form
        return context


class OaiCommunityUpdateView(UpdateView):
    model = Community
    template_name = 'oai_collection_form.html'
    fields = ['name']

    def get_context_data(self, **kwargs):
        context = super(OaiCommunityUpdateView, self).get_context_data(**kwargs)        
        context['view_type'] = 'update community collection info'
        return context


class OaiCommunityDeleteView(DeleteView):
    model = Community
    template_name = 'oai_confirm_delete.html'
    success_url = reverse_lazy('oai_repository_list')

    def get_context_data(self, **kwargs):
        context = super(OaiCommunityDeleteView, self).get_context_data(**kwargs)        
        context['view_type'] = 'delete community collection'
        return context


class OaiCommunityHarvestView(DetailView):
    model = Community
    template_name = 'oai_community_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super(OaiCommunityHarvestView, self).get_context_data(**kwargs)
        oai = OAIUtils()
        community = self.get_object()
        batch_harvest_issues(community)
        context['collections'] = community.list_collections()
        return context


class OaiCollectionView(DetailView):
    model = Collection
    template_name = 'oai_collection_detail.html'

    def get_context_data(self, **kwargs):
        context = super(OaiCollectionView, self).get_context_data(**kwargs)
        context['num_records'] = self.get_object().count_records()
        context['records'] = self.get_object().record_set.all()
        return context


class OaiCollectionCreateView(CreateView):
    """Creates a db object for a specific collection. Listed options are 
    derived from a listing of collections from the community."""
    model = Collection
    template_name = 'oai_collection_form.html'
    form_class = CreateCollectionForm
    community = None    

    def get(self, request, *args, **kwargs):
        self.community = Community.objects.get(pk=self.kwargs.get('community')) 
        return super(OaiCollectionCreateView, self).get(request, *args, **kwargs)

    def post(self, request, **kwargs):
        self.community = Community.objects.get(pk=self.kwargs.get('community'))    
        return super(OaiCollectionCreateView, self).post(request, **kwargs)

    def get_form_kwargs(self):
        kwargs = super(OaiCollectionCreateView, self).get_form_kwargs()
        oai = OAIUtils()
        collections = oai.list_oai_collections(self.community)
        collections = filter_existing_collections(collections)
        kwargs['community'] = self.community
        kwargs['collection_list'] = collections
        return kwargs

    def form_valid(self, form):            
        choices = form.fields['identifier'].widget.choices
        for i in choices:
            if i[0] == form.instance.identifier:
                form.instance.name = i[1]
                break
        form.save()
        return HttpResponseRedirect(reverse('oai_collection', args=[str(form.instance.identifier)]))        

    def get_success_url(self):
        success_url = reverse('oai_community', args=[str(self.community.identifier)])
        return success_url

    def get_context_data(self, **kwargs):
        context = super(OaiCollectionCreateView, self).get_context_data(**kwargs)        
        context['view_type'] = 'add new collection'
        return context


class OaiCollectionUpdateView(UpdateView):
    model = Collection
    template_name = 'oai_collection_form.html'
    fields = ['name']

    def get_context_data(self, **kwargs):
        context = super(OaiCollectionUpdateView, self).get_context_data(**kwargs)        
        context['view_type'] = 'update collection info'
        return context


class OaiCollectionDeleteView(DeleteView):
    model = Collection
    template_name = 'oai_confirm_delete.html'
    success_url = reverse_lazy('oai_repository_list')

    def get_context_data(self, **kwargs):
        context = super(OaiCollectionDeleteView, self).get_context_data(**kwargs)        
        context['view_type'] = 'delete collection info'
        return context


class OaiCollectionHarvestView(DetailView):
    model = Collection
    template_name = 'oai_collection_detail.html'

    def get(self, request, *args, **kwargs):
        collection = self.get_object()
        batch_harvest_articles(collection)
        collection.save()
        # return redirect('oai_collection', pk=collection.pk)
        return HttpResponse('OK')

# http://scholarspace.manoa.hawaii.edu/dspace-oai/request?verb=GetRecord&identifier=oai:scholarspace.manoa.hawaii.edu:10125/24502&metadataPrefix=oai_dc

# Sample request for a single collection
# http://scholarspace.manoa.hawaii.edu/dspace-oai/request?verb=ListRecords&metadataPrefix=oai_dc&set=col_10125_7735

# Sample request for a set listRecords
# http://scholarspace.manoa.hawaii.edu/dspace-oai/request?verb=ListIdentifiers&metadataPrefix=oai_dc&set=col_10125_7735
