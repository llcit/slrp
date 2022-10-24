# utils.py

""" 
OAIUtils : A set of utility functions that handle requests and format responses for OAI provider. 

http://www.openarchives.org/OAI/openarchivesprotocol.html
"""
import os
import io
import json
import time
import requests

from django.utils import timezone, dateparse

from oaipmh.client import BaseClient, Client
from oaipmh.metadata import MetadataRegistry, oai_dc_reader

# Sickle implementation: https://sickle.readthedocs.io/en/latest/
import string, urllib
from collections import defaultdict

from sickle import Sickle
from sickle.utils import xml_to_dict, get_namespace
from sickle.models import Record, Header

from .models import Collection, Record as LocalRecord, MetadataElement



def filter_existing_collections(collections):
    """ Returns a list of tuples containing collections not present in local db."""
    collections_filtered = []
    cols = Collection.objects.all()
    for i in collections:
        if not cols.filter(identifier=i[0]):
            collections_filtered.append(i)
    return collections_filtered

def dim_xml_to_dict(tree):
    fields = defaultdict(list)
    for tag in tree.getchildren():
        f = tag.get('element')
        q = tag.get('qualifier')
        if q: f += '.' + q
        fields[f].append(tag.text)    
    return dict(fields)

def get_bitstream_url(collection, record_in):
    """ Harvests an href pointing to the bitstream urls for the record in repository.
    E.g., https://scholarspace.manoa.hawaii.edu/bitstream/10125/25006/1/editor.pdf
    """
    bitstreams = {'bitstream': None, 'bitstream_txt': None, 'bitstream_extra': None}
    try:
        sickle = Sickle(collection.community.repository.base_url)        
        sickle.class_mapping['GetRecord'] = LltRecordBitstream_v2
        record = sickle.GetRecord(metadataPrefix='ore', identifier=record_in.header.identifier)
        print (record.metadata)
    except Exception as e:
        print (e)
        return bitstreams
    
    try:  
        bitstreams['bitstream'] = record.metadata['bitstream']      
        # bitstreams['bitstream'] = record.metadata['bitstream'][0].replace('+', '%20')
    except Exception as e:
        print (e, 'Unable to construct bitstream url for', record_in.header.identifier)

    try:
        bitstreams['bitstream_txt'] = record.metadata['bitstream_txt']
        # bitstreams['bitstream_txt'] = record.metadata['bitstream_txt'][0].replace('+', '%20')
    except Exception as e:
        print (e, 'Unable to construct bitstream_txt url for', record_in.header.identifier)
    
    try:
        bitstreams['bitstream_extra'] = record.metadata['bitstream_extra']
    except Exception as e:
        print (e, 'Unable to construct bitstream_extra urls for', record_in.header.identifier)

    return bitstreams

def batch_harvest_articles(collection_obj):
    oai = OAIUtils()
    records = oai.harvest_oai_collection_records_sickle(collection_obj)

    for record in records:
        # Read Header
        if not record.header.deleted:
            repo_date = dateparse.parse_datetime(record.header.datestamp)
            try:
                record_obj = LocalRecord.objects.get(identifier=record.header.identifier)            
                record_obj.remove_data()
                record_obj.hdr_datestamp = repo_date

            except Exception as e:
                record_obj = LocalRecord()
                record_obj.identifier = record.header.identifier
                record_obj.hdr_datestamp = repo_date
                record_obj.hdr_setSpec = collection_obj
            
            record_obj.save()

            # Read Metadata
            dataelements = record.metadata
            for key in dataelements:
                element = MetadataElement()
                element.record = record_obj
                element.element_type = key
                data = dataelements[key]
                element.element_data = json.dumps(data)
                element.save()

            #  Add in bitstream urls
            bitstreams = get_bitstream_url(collection_obj, record)
            element = MetadataElement()
            element.record = record_obj
            element.element_type = 'bitstream'
            element.element_data = json.dumps([bitstreams['bitstream']])
            element.save()

            element = MetadataElement()
            element.record = record_obj
            element.element_type = 'bitstream_txt'
            element.element_data = json.dumps([bitstreams['bitstream_txt']])
            element.save()
        else:
            try:
                record_obj = LocalRecord.objects.get(identifier=record.header.identifier)
                record_obj.delete()     
            except:
                pass

def batch_harvest_issues(community_obj):
    oai = OAIUtils()
    issues = oai.list_oai_collections(community_obj)
    for i in issues:
        col = Collection(identifier=i[0], name=i[1], community=community_obj)
        try:
            col.save()
        except Exception as e:
            # collection already added to db
            col = Collection.objects.get(identifier=i[0])
        
        batch_harvest_articles(col)
        time.sleep(5)

def build_bitstream_txt_paths(records=None):
    paths = []
    errors = []
    if not records:
        records = LocalRecord.objects.all()
    
    for r in records:
        rd = r.as_dict()
        try:
            if rd['collection'][0].identifier != 'col_10125_54598':
                d = {'rec_obj': r,'title': rd['title'][0], 'bitstream_txt':rd['bitstream_txt'][0]}
                paths.append(d)

        except Exception as e:
            print(e)
            errors.append((r.pk, r.identifier, rd['title'][0], rd['volume'][0], rd['number']))
    return (paths, errors)

def batch_load_full_text(local_dir=None):
    recs = LocalRecord.objects.all()
    for rec in recs:
        res = rec.load_full_text(local_dir)
        if res:
            print(res)
        time.sleep(2)

def download_full_text_files(data_dir=None):
    if not data_dir: 
        print('data directory not specified')
        return
    
    paths = build_bitstream_txt_paths()[0]
    path_errs = []
    for i, p in enumerate(paths):    
        file_name = None
        url = None        

        try:
            url = p.get('bitstream_txt')
            url = url.replace('http://', 'https://')
            file_name = url.split('/')[-1]
            file_name = os.path.join(data_dir, file_name)
        except Exception as e:
            path_errs.append(('URL ERROR', i, url, file_name))
            print (i, 'URL ERROR')
            continue 

        if os.path.isfile(file_name):
            continue
        
        try:
            r = requests.get(url, timeout=1.0)
            txt = r.text
            with io.open(file_name, 'w', encoding='utf8') as f:
                f.write(txt)
                print ('\t wrote', i, url, file_name)
            time.sleep(5)
        except Exception as e:
            path_errs.append(('REQUEST ERROR', i, url, file_name))
            print('REQUEST ERROR')

    with open(os.path.join(data_dir, 'bitstream_path_errors.json'), 'w') as ferror:
        ferror.write(json.dumps(path_errs, indent=2))

def export_records(community_obj):
    collections = community_obj.list_collections()
    data_rows = []
    for i in collections:
        recs = i.list_records()
        for r in recs:
            rd = r.as_dict()
            try:
                desc = rd['description.abstract'][0]
            except:
                desc = ''
            d = (rd['volume'][0], rd['identifier.uri'][0], rd['title'][0], rd['startingpage'][0], rd['endingpage'][0], desc )
            data_rows.append(d)

    return data_rows

class LltRecord(Record):
    """ XML Record handler override for dim metadata format. """    
    def __init__(self, record_element, strip_ns=True):
        super(LltRecord, self).__init__(record_element, strip_ns=strip_ns)
        self.header = Header(self.xml.find('.//' + self._oai_namespace + 'header'))
        if not self.header.deleted:
            tree = self.xml.find('.//' + self._oai_namespace + 'metadata').getchildren()[0]
            self.metadata = dim_xml_to_dict(tree)


class LltRecordBitstream(Record):
    """ XML Record handler override for ore metadata format. Used to retrieve bitstream url for a record."""    
    def __init__(self, record_element, strip_ns=True):
        super(LltRecordBitstream, self).__init__(record_element, strip_ns=strip_ns)
        self._oai_namespace = get_namespace(self.xml)
        rdfnamespace = '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}'

        tree = self.xml.find('.//' + self._oai_namespace + 'metadata').getchildren()[0]
        bitstream_urls = tree.findall('.//'+rdfnamespace+'Description')

        # for debugging in shell
        self.bits = bitstream_urls
        
        #  clear the metadata. we're only interested in fishing out the bitstream info.
        self.metadata.clear()
        
        for i in bitstream_urls:
            bittype = i.find(rdfnamespace+'type').get(rdfnamespace+'resource')

            if bittype != 'http://www.dspace.org/objectModel/DSpaceItem':
                biturl = i.get(rdfnamespace+'about')
                if biturl[-3:] == 'pdf':
                    self.metadata['bitstream'] = [biturl]
                else:
                    self.metadata['bitstream_txt'] = [biturl]
        
        # for i in bitstream_urls:
        #     print i
        #     # if i.get('rel') == 'http://www.openarchives.org/ore/terms/aggregates':
            #     self.metadata = {'bitstream': [i.get('href')]}


class LltRecordBitstream_v2(Record):
    """ XML Record handler override for ore metadata prefix (format). Used to retrieve bitstream urls for a record."""    
    def __init__(self, record_element, strip_ns=True):
        super(LltRecordBitstream_v2, self).__init__(record_element, strip_ns=strip_ns)
        self._oai_namespace = get_namespace(self.xml)
        atom_ns = '{http://www.w3.org/2005/Atom}'
        dc_ns = '{http://purl.org/dc/terms/}'
        rdf_ns = '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}'

        tree = self.xml.find('.//' + self._oai_namespace + 'metadata').getchildren()[0]
        
        doc_urls = tree.findall('.//'+atom_ns+'link') # Retrieves file/url info for primary bitstreams
        txt_urls = tree.findall('.//'+rdf_ns+'Description') # Retrieves file/url info for ocr'ed files

        doc_bitstreams = [] # url for primary document/article pdf
        txt_bitstreams = [] # url for ocr'ed pdf documents
        extra_bitstreams = [] # urls for secondary data files.

        for i in doc_urls:
            link_type = i.get('rel')
            if link_type == 'http://www.openarchives.org/ore/terms/aggregates':
                href = i.get('href')
                ftype = i.get('type')
                ftitle = i.get('title')
                # To do: determine if supplemental file based on 'supplemental' key
                doc_bitstreams.append(href)

        for i in txt_urls:
            link_type = i.find(rdf_ns+'type').get(rdf_ns+'resource')
            if link_type != 'http://www.dspace.org/objectModel/DSpaceItem':
                href = i.get(rdf_ns+'about')
                ftype = ''
                try:
                    ftype = i.find(dc_ns+'description').text
                except Exception as e:
                    pass
                if ftype == 'TEXT':
                    txt_bitstreams.append(href)

        self.metadata.clear() # clear the metadata. we're only interested in fishing out the bitstream info.
        self.metadata['bitstream'] = doc_bitstreams
        self.metadata['bitstream_txt'] = txt_bitstreams
        

class OAIUtils(object):
    """ Provides an api for interacting with and harvesting from the 
    OAI repository. Utilizes the sickle module as a wrapper for requests.
    """

    def __init__(self):
        self.repositories = []
        self.communities = []
        self.collections = []

    def list_oai_community_sets(self, repository):
        """ Contructs list of tuples of communities (a grouping concept in OAI) 
        for the given repository.
        Utilizes OAI-PMH verb: ListSets
        """
        try:
            sickle = Sickle(repository.base_url)
            sets = sickle.ListSets()
        except:
            return

        """ Filter set list to build list of community sets """
        for i in sets:
            """ Build community tuples (id, human readable name) """
            if i.setSpec[:3] == 'com':
                set_data = (i.setSpec, i.setName)
                self.communities.append(set_data)

        self.communities = sorted(self.communities, key=lambda i: i[1])

    def list_oai_collections(self, community):
        """ Constructs list of tuples of collections (a seconday grouping concept
        in OAI) "owned" by the given community.
        
        Utilizes OAI-PMH verbs: ListIdentifiers and ListSets
        """
        sickle = Sickle(community.repository.base_url)
        
        # Retrieve collections associated with community parameter
        record_headers = sickle.ListIdentifiers(metadataPrefix='oai_dc', set=community.identifier)

        # Filter record headers to build collection map from the community
        community_collections = {}  
        for i in record_headers:
            # Iterate over associated sets looking for collections 
            for j in i.setSpecs:     
                if j[:3] == 'col':
                    community_collections[j] = None  # register collection id 

        # Map names to ids in collection map {setSpec: setName}
        # listsets oai request returns the 'setName' of the collection in metadata...       
        for i in sickle.ListSets():
            if i.setSpec in community_collections: # checks for a mapped collection identifier                
                community_collections[i.setSpec] = i.setName

        # Convert map to list of tuples
        self.collections = community_collections.items()

        # Sort collections by name
        self.collections = sorted(self.collections, key=lambda i: i[1])
        return self.collections

    def harvest_oai_collection_records_sickle(self, collection):
        sickle = Sickle(collection.community.repository.base_url)
        sickle.class_mapping['ListRecords'] = LltRecord
        sickle.class_mapping['GetRecord'] = LltRecord
        records = sickle.ListRecords(metadataPrefix='dim', ignore_deleted=True, set=collection.identifier)
        return records


    def test_list_oai_collections(self, community):
        """ Constructs list of tuples of collections (a seconday grouping concept
        in OAI) "owned" by the given community.
        
        Utilizes OAI-PMH verbs: ListIdentifiers and ListSets
        """
        sickle = Sickle(community.repository.base_url)
        
        # Retrieve collections associated with community parameter
        record_headers = sickle.ListIdentifiers(metadataPrefix='oai_dc', set=community.identifier)
        # Filter record headers to build collection map from the community
        community_collections = {}  
        for i in record_headers:
            # Iterate over associated sets looking for collections 
            for j in i.setSpecs:     
                if j[:3] == 'col':
                    community_collections[j] = None  # register collection id in map

        # Map names to ids in collection map {setSpec: setName}
        # listsets oai request returns the 'setName' of the collection in metadata...       
        for i in sickle.ListSets():
            modstr = 'col' + i.setSpec[3:] # Bug in oai? in set results a 'collection' has a prefix of 'com'!
            if modstr in community_collections: # checks for a mapped collection identifier
                community_collections[modstr] = i.setName

        # Convert map to list of tuples
        self.collections = community_collections.items()

        # Sort collections by name
        self.collections = sorted(self.collections, key=lambda i: i[1])
        return self.collections
