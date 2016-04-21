""" Welborn Productions - Stats - urls
    Provides the urls needed to access the stats page.
"""
from django.conf.urls import patterns, url

from stats.views import view_index

urlpatterns = patterns(
    '',
    url(r'^$', view_index)
)

# TODO: Allow finer-grain stats pages. URL would point to a specific stats page
#       like: welbornprod.com/stats/wp_project
