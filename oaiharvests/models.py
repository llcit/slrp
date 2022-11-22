from django.db import models
from django.urls import reverse
from datetime import date
from model_utils.models import TimeStampedModel
from collections import OrderedDict, defaultdict

import json, operator, os, requests, io
import pdb #pdb.set_trace()


"""Metadata element dispay sets"""

TYPES = ['publisher', 'description.provenance', 'identifier.doi', 'title', 'bitstream', 'date.available', 'type.dcmi', 'relation.uri', 'identifier.citation', 'format.extent', 'description.abstract', 'date.accessioned', 'language.iso', 'relation.ispartofseries', 'identifier.issn', 'date.issued', 'identifier.uri', 'type', 'contributor.author', 'subject', 'volume', 'startingpage', 'llt.topic']

DISPLAY_TYPE_ORDER = ['title', 'contributor.author', 'description.abstract', 'bitstream', 'bitstream_txt', 'subject', 'publisher', 'type', 'relation.ispartofseries', 'date.issued', 'identifier.doi', 'identifier.uri', 'identifier.citation', 'volume', 'startingpage', 'endingpage']


class Repository(TimeStampedModel):

    """ A institutional digital library OAI service provider -- e.g., ScholarSpace """

    name = models.CharField(max_length=256)
    base_url = models.URLField(unique=True)

    def list_communities(self):
        return self.community_set.all()

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('oai_repository', args=[str(self.id)])


class Community(TimeStampedModel):

    """A hierarchical organization of sets -- e.g., Language Learning & Technology is a community collection"""

    identifier = models.CharField(primary_key=True, max_length=256)
    name = models.CharField(max_length=256, blank=True, default=None)
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE)

    
    def list_collections(self):
        return self.collection_set.all().order_by('-name')

    def list_collections_by_volume(self):
        # TODO: return collections grouped by volume number.
        volumes_group = OrderedDict()
        volumes = self.collection_set.all().order_by('-name')
        for i in volumes:
            # get a record from the volume
            rec = i.list_records()[0]
            
            # get volume number from record
            try:
                # print '===>', rec, rec[2]
                vol_num = int(rec.get_metadata_item('volume')[0][0])
            except Exception as e:
                vol_num = 0

            # add volume num as dict key
            if vol_num in volumes_group:
                volumes_group[vol_num].append(i)
            else:
                volumes_group[vol_num] = [i]

        return volumes_group

    def aggregate_keywords(self):
        keywords = []
        for i in MetadataElement.objects.all().filter(element_type='subject'):
            keywords.extend(json.loads(i.element_data))
        return sorted(keywords)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('oai_community', args=[str(self.identifier)])


class Collection(TimeStampedModel):

    """Models the OAI standard conception of a SET"""

    identifier = models.CharField(primary_key=True, max_length=256)
    name = models.CharField(max_length=256, blank=True)
    community = models.ForeignKey(Community, null=True, blank=True, on_delete=models.CASCADE)
    last_harvest = models.DateTimeField(auto_now=True)

    def title_tuple(self):
        """Parses name of collection to enumerate 'special issue' titles if they exist.
        """
        q = 'special issue'
        title = (self.name, '')
        pos = self.name.lower().find(q)
        if pos >= 0:
            a = self.name[:pos].strip()
            b = self.name[pos:]
            title = (a, b)
            
        return title

    def get_publication_date(self):
        try:
            sample_rec = self.record_set.all()[0]
            pdate = sample_rec.get_metadata_item('date.issued')[0][0];
            return date.fromisoformat(pdate).strftime('%b %d %Y')

        except Exeption as e:
            print(e)
            return ''

    def count_records(self):
        return self.record_set.all().count()

    def list_records(self):
        return self.record_set.all()

    def list_records_by_page_and_volume(self):
        records = []
        for i in self.record_set.all():
            record_data = i.as_display_dict()
            t = [i]
            
            try:
                t.append(int(record_data['startingpage'][0]))
            except Exception as e:
                t.append(0)

            try:
                t.append(int(record_data['endingpage'][0]))
            except Exception as e:
                t.append(0)

            try:
                t.append(record_data['volume'][0])
            except Exception as e:
                t.append('0')
            # print t, '\n'
            records.append(t)

        return sorted(records, key=lambda rec: rec[1])

    def list_toc(self):
        toc = defaultdict(list)
        for i in self.list_records():
            d = i.as_dict()
            try:
                for j in d['type']:  # Build toc data.
                    try:
                        authors = d['contributor.author']
                        authors = [k.split(',')[1] + ' ' + k.split(',')[0] for k in authors]
                        try:
                            toc[j].append((i, authors, d['description.abstract'], d['startingpage']))
                        except KeyError:
                            toc[j].append((i, authors, ''))
                    except:
                        toc[j].append((i, '', ''))
            except:
                pass
        return toc

    def list_toc_by_page(self):
        """Returns a dictionary that groups record objects by type of record.
        A type is but not limited to: FRONT MATTER, ARTICLE, COLUMN, or REVIEW.
        Each record is a list with the following the format:

        TODO: Modify each record item as dict by subtopic: <llt.topic> or 'BASIC': [REC OBJECT ...]
        {TYPE_NAME: [ [REC OBJECT, AUTHOR LIST, ABSTRACT TEXT, PAGE START], ... ]}
        """
        toc = defaultdict()
        # toc = {}

        for rec in self.list_records_by_page_and_volume():  # Returns a list of [ [REC OBJ, PAGE START, PAGE END, VOL NUM], ... ]
            rec_obj = rec[0]       # Record object
            rec_data = rec_obj.as_dict()  # Fetch the record data
            # print rec, rec_data['type'], rec_data['llt.topic'] or None
            try:
                for rec_type in rec_data['type']:
                    toc_item = [rec_obj, [], [], '']  # Set defaults (rec object, authors, abstract, start page)
                    
                    # Build author list 
                    try:
                        authors = rec_data['contributor.author'] # Pretty print author list (first, last)
                        authors = [k.split(',')[1] + ' ' + k.split(',')[0] for k in authors]
                        toc_item[1] = authors
                    except:
                        pass  # Problem parsing authors but default already set to empty.
                    
                    # Build editor list
                    try:
                        editors = rec_data['contributor.editor'] # Pretty print editor list (first last)
                        try:  # handle error related to metadata entry for first name, last name
                            editors = [k.split(',')[1] + ' ' + k.split(',')[0] for k in editors]
                        except:
                            pass
                    except Exception as e:
                        editors = []  # Problem parsing editors, set to empty. 
                        # Possible issue: Check that editor name is entered as <last name>, <first name> in metadata.

                    # Add abstract text 
                    try:
                        toc_item[2] = rec_data['description.abstract']
                    except:
                        pass  # Problem fetching abstract but default already set to empty.
                    
                    # Fetch page number from list if not zero
                    if rec[1]: toc_item[3] = rec[1]  

                    # Get subtopic (llt.topic)
                    try:
                        rec_subtype = rec_data['llt.topic'][0]
                    except:
                        rec_subtype = ''

                    # Group according to record type...
                    try:
                        toc[rec_type]
                    except KeyError:
                        toc[rec_type] = OrderedDict()
                    
                    try:
                        toc[rec_type][rec_subtype]['records'].append(toc_item)
                        editor_set = toc[rec_type][rec_subtype]['editors']
                        editor_set.set(editor_set.extend(editors))
                        toc[rec_type][rec_subtype]['editors'] = list(editor_set)
                    except KeyError:
                        toc[rec_type][rec_subtype] = {'editors': [], 'records': []}
                        toc[rec_type][rec_subtype]['editors'].extend(editors)
                        toc[rec_type][rec_subtype]['records'].append(toc_item)
                        
            except Exception as e:
                pass  # record must not have a type specified so proceed quietly
        
        return toc

    def get_absolute_url(self):
       return reverse('collection', args=[str(self.identifier)])

    def __str__(self):
        return self.name


class Record(TimeStampedModel):
    """OAI conception of an ITEM"""
    identifier = models.CharField(max_length=256, unique=True)
    hdr_datestamp = models.DateTimeField()
    hdr_setSpec = models.ForeignKey(Collection, on_delete=models.CASCADE)
    full_text = models.TextField(default='')

    def remove_data(self):
        MetadataElement.objects.filter(record=self).delete()
        return

    def get_metadata_item(self, e_type):
        data = []
        elements = self.data.filter(element_type=e_type)
        for e in elements:
            data.append(json.loads(e.element_data))
        return data

    def metadata_items(self):
        return self.data.all()

    def metadata_items_json(self):
        json_metadata = {}
        for e in self.metadata_items():
            jsonobj = json.loads(e.element_data)
            if jsonobj:
                json_metadata[e.element_type]=jsonobj
            else:
                json_metadata[e.element_type]=['']
        
        return json_metadata

    # Sort record dictionary by key
    def sort_metadata_dict(self, record_dict):
        return OrderedDict(sorted(record_dict.items(), key=lambda t: t[0]))

    def as_dict(self):
        record_dict = {}
        elements = self.data.all().order_by('element_type')
        # print elements
        for e in elements:
            data = json.loads(e.element_data)
            record_dict[e.element_type] = data
        record_dict['collection'] = [self.hdr_setSpec]
        record_dict['site_url'] = [self.get_absolute_url()]
        
        return self.sort_metadata_dict(record_dict)

    def as_dict_string_format(self):
        record_dict = {}
        record_str = ''
        elements = self.data.all().order_by('element_type')
        # print elements
        for e in elements:
            data = json.loads(e.element_data)
            try:
                record_str += u'; '.join(data) + ' '
            except:
                record_str += str(data) + ' '

        record_str += self.hdr_setSpec.name + '  '
        record_str += self.get_absolute_url() + ' '
        
        return record_str

    def as_display_dict(self):
        record_dict = self.as_dict()
        display_dict = OrderedDict()
        for tag in DISPLAY_TYPE_ORDER:
            try:
                t = tag.split('.')
                if len(t) > 1:
                    display_dict[t[1]] = record_dict[tag]
                else:
                    display_dict[tag] = record_dict[tag]
            except:
                pass
        return display_dict

    def get_keyword_list(self):
        try:
            return rec.get_metadata_item('subject')[0][0]
        except:
            return []

    def get_readable_authors(self):
        try:
            authors = self.get_metadata_item('contributor.author')[0]
            authors = [k.split(',')[1] + ' ' + k.split(',')[0] for k in authors]
            return authors
        except Exception as e:
            return []        

    def load_full_text(self, local_dir=None):
        url = None
        meta_data = self.as_dict()
        if local_dir:            
            try:
                bitstream_txt = meta_data.get('bitstream_txt')[0]
                url = os.path.join(local_dir, bitstream_txt.split('/')[-1])
                with io.open(url, 'r', encoding='utf8') as f:
                    t = f.read()
                    self.full_text = t.replace(u'\x00', '')
                    self.save()
            except Exception as e:
                return (self.pk, url, e)
        else:
            try:
                url = meta_data.get('bitstream_txt')[0]
                url = url.replace('http://', 'https://')
                r = requests.get(url, timeout=1.0)
                self.full_text = r.text
                self.save()
            except Exception as e:
                return (self.pk, url, e)
        
        return None

    def __str__(self):
        title = self.get_metadata_item('title')[0][0]
        return '%s'%(title)

    def get_absolute_url(self):
        return reverse('item', args=[str(self.id)])
    

class MetadataElement(models.Model):

    """A tuple containing an element_type (dublin core) and its data"""
    record = models.ForeignKey(Record, null=True, related_name='data', on_delete=models.CASCADE)
    element_type = models.CharField(max_length=256)
    element_data = models.TextField(default='')

    def __str__(self):
        return u'%s:%s'%(self.element_type, self.element_data)

    def get_absolute_url(self):
        reverse('item', args=[self.record.id])


class HarvestRegistration(TimeStampedModel):
    """ Records of harvested collections """
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    harvest_date = models.DateTimeField()
