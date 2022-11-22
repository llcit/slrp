from django.conf.urls import include, url
from django.contrib import admin

from django.contrib.auth import views as auth_views

admin.autodiscover()

from filebrowser.sites import site


from lltsite.views import (
    HomeView, 
    PreviousIssuesView,
    CommunityView, 
    CollectionListView, 
    CollectionView, 
    ItemView, 
    ItemViewFull,
    PageView,
    PageUpdateView,
    PageViewPrivate,
    KeywordBrowseView,
    SearchHaystackView,
    SubscriberCreateView,
    SubscriberListView,
    SubscriberListCsvView,
    UpdateImpactFactorView,
    LatestEntriesFeed
)

from oaiharvests.views import (
    OaiRepositoryListView, 
    OaiRepositoryCreateView, 
    OaiRepositoryUpdateView, 
    OaiRepositoryDeleteView, 
    OaiRepositoryView,
    OaiCommunityView,
    OaiCommunityCreateView,
    OaiCommunityUpdateView,
    OaiCommunityDeleteView,
    OaiCommunityHarvestView,
    OaiCollectionView,
    OaiCollectionCreateView,
    OaiCollectionUpdateView,
    OaiCollectionDeleteView,
    OaiCollectionHarvestView
)

urlpatterns = [

   # ---------- SITE VIEWS ------------- #

    url(r'^$', HomeView.as_view(), name='home'),

    url(r'^previous-issues/$',
     PreviousIssuesView.as_view(), name='previous_issues'),

    url(r'^community/(?P<pk>\w+)$',
     CommunityView.as_view(), name='community'),                       

    url(r'^collections/$', CollectionListView.as_view(),
     name='collection_list'),

    url(r'^collection/(?P<pk>\w+)$',
     CollectionView.as_view(), name='collection'),

    url(r'^item/(?P<pk>\d+)$',
     ItemView.as_view(), name='item'),

    url(r'^item-detail/(?P<pk>\d+)$',
     ItemViewFull.as_view(), name='item_full'),

    url(r'^page/(?P<pk>\d+)/$',
     PageView.as_view(), name='page_view'),

    url(r'^page/edit/(?P<pk>\d+)/$',
     PageUpdateView.as_view(), name='page_update_view'),

    url(r'^keys/$',
     KeywordBrowseView.as_view(), name='keyword_browse_view'),

    url(r'^staff-page/(?P<pk>\w+)$',
     PageViewPrivate.as_view(), name='staff_page_view'),

    url(r'^search/$',
       SearchHaystackView.as_view(), name='haystack_search'),

    url(r'^subscribe/$',
       SubscriberCreateView.as_view(), name='subscribe'),

    url(r'^subscribers/(?P<alpha_index>[A-Za-z0-9])/$',
       SubscriberListView.as_view(), name='subscriber_list'),

    url(r'^subscribers/download-list/$',
       SubscriberListCsvView.as_view(), name='subscriber_list_csv'),    

    url(r'^update-impact-factor/(?P<pk>\d+)$',
       UpdateImpactFactorView.as_view(), name='update_factor'),    

    # url(r'^searchtest/$',
    #    SearchPage.as_view(), name='searchtest'),

    # url(r'^search/', include('haystack.urls')),



    # ---------- OAI HARVESTER VIEWS ------------- #
    # Institutional Repositories #
    url(r'^oaiharvester/$', OaiRepositoryListView.as_view(),
     name='oai_repository_list'),
    url(r'^oaiharvester/repository/add/$',
     OaiRepositoryCreateView.as_view(
     ), name='oai_repository_add'),
    url(r'^oaiharvester/repository/edit/(?P<pk>\w+)$',
     OaiRepositoryUpdateView.as_view(
     ), name='oai_repository_edit'),
    url(r'^oaiharvester/repository/delete/(?P<pk>\w+)$',
     OaiRepositoryDeleteView.as_view(
     ), name='oai_repository_delete'),
    url(r'^oaiharvester/repository/(?P<pk>\w+)$',
     OaiRepositoryView.as_view(), name='oai_repository'),

    # Community Collections #
    url(r'^oaiharvester/community/(?P<pk>\w+)$',
     OaiCommunityView.as_view(), name='oai_community'),
    url(r'^oaiharvester/community/add/(?P<pk>\w+)$',
     OaiCommunityCreateView.as_view(
     ), name='oai_community_add'),
    url(r'^oaiharvester/community/edit/(?P<pk>\w+)$',
     OaiCommunityUpdateView.as_view(
     ), name='oai_community_edit'),
    url(r'^oaiharvester/community/delete/(?P<pk>\w+)$',
     OaiCommunityDeleteView.as_view(
     ), name='oai_community_delete'),
    url(r'^oaiharvester/community/harvest/(?P<pk>\w+)$',
     OaiCommunityHarvestView.as_view(
     ), name='oai_harvest_community'),

    # Collections #
    url(r'^oaiharvester/collection/(?P<pk>\w+)$',
     OaiCollectionView.as_view(), name='oai_collection'),
    url(r'^oaiharvester/collection/add/(?P<community>\w+)$',
     OaiCollectionCreateView.as_view(
     ), name='oai_collection_add'),
    url(r'^oaiharvester/collection/edit/(?P<pk>\w+)$',
     OaiCollectionUpdateView.as_view(
     ), name='oai_collection_edit'),
    url(r'^oaiharvester/collection/delete/(?P<pk>\w+)$',
     OaiCollectionDeleteView.as_view(
     ), name='oai_collection_delete'),
    url(r'^oaiharvester/collection/harvest/(?P<pk>\w+)$',
     OaiCollectionHarvestView.as_view(
     ), name='oai_harvest_collection'),


    url(r'^feed/', LatestEntriesFeed()),

    url(r'^admin/filebrowser/', site.urls),
    url(r'^grappelli/', include('grappelli.urls')), # grappelli URLS
    url(r'^admin/', admin.site.urls, name='index'),

    url(r'^login/$', auth_views.LoginView.as_view(), name='login_user'),
    url(r'^logout/$', auth_views.LogoutView.as_view(next_page='/'), name='logout_user'),

    url(r'^(?P<slug>[-\w]+)/$',
     PageView.as_view(), name='page_slug_view'),

]
