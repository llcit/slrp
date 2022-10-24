# oaiharvests/forms.py
from django.forms import ModelForm, ValidationError
from django import forms
from django.contrib import messages

from oaipmh.client import Client
from oaipmh.metadata import MetadataRegistry, oai_dc_reader

from .models import Repository, Community, Collection
from .utils import OAIUtils, filter_existing_collections

class CreateRepositoryForm(ModelForm):

    def clean(self):
        cleaned_data = super(CreateRepositoryForm, self).clean()
        try:
            registry = MetadataRegistry()
            registry.registerReader('oai_dc', oai_dc_reader)
            client = Client(cleaned_data.get('base_url'), registry)
            server = client.identify()
            # set the repository name apply to model instance when saved.
            cleaned_data['name'] = server.repositoryName()
        except:
            raise ValidationError('Repository base url is invalid.')

        return cleaned_data

    def save(self):
        repository = super(CreateRepositoryForm, self).save(commit=False)
        repository.name = self.cleaned_data.get('name')
        repository.save()
        return repository

    class Meta:
        model = Repository
        fields = ['base_url']


class CreateCommunityForm(ModelForm):

    def __init__(self, *args, **kwargs):
        try:
            repo = kwargs.pop('repo')
            communities = kwargs.pop('community_list')
        except:
            pass

        super(CreateCommunityForm, self).__init__(*args, **kwargs)

        self.fields['identifier'] = forms.CharField(
            widget=forms.Select(choices=communities))
        self.fields['identifier'].label = 'Select Community Collection From ' + \
            repo.name + ':'
        self.fields['repository'].initial = repo
        self.fields['repository'].empty_label = None
        self.fields['repository'].label = repo.name

    class Meta:
        model = Community
        fields = ['identifier', 'name', 'repository']
        widgets = {'name':
                   forms.HiddenInput(), 'repository': forms.HiddenInput()}


class CreateCollectionForm(ModelForm):

    def __init__(self, *args, **kwargs):
        
        try:
            collections = kwargs.pop('collection_list')
            community = kwargs.pop('community')
        except Exception as e:
            print(e)
            
        super(CreateCollectionForm, self).__init__(*args, **kwargs)
        self.fields['identifier'] = forms.CharField(widget=forms.Select(choices=collections))
        self.fields['identifier'].label = 'Select Collection From ' + community.name + ':'
        self.fields['community'].initial = community
        self.fields['community'].label = community.name

    class Meta:
        model = Collection
        fields = ['identifier', 'community']
        widgets = {
            'identifier': forms.Select(choices=[]),
            'community': forms.HiddenInput()
        }
        
