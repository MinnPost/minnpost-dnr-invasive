#!/usr/bin/env python
"""
Fab file to help with managing project.  For docs on Fab file, please see: http://docs.fabfile.org/

For exporting tiles to s3 and processing data
"""
import sys
import os
import warnings
import json
import re
import urllib2
import csv
import json

from fabric.api import *

"""
Base configuration
"""
env.project_name = 'minnpost-dnr-invasive'


def vdata_load_data():
  """
  Load viz data.
  """
  path = os.path.dirname(__file__)
  json_file = os.path.join(path, '../visualizations/data/species-metadata.json')
  json_file_object = open(json_file, 'r')
  json_data = json_file_object.read()
  json_file_object.close()
  env.vdata_json = json.loads(json_data)


def vdata_save_data():
  """
  Save viz data.
  """
  require('vdata_json')
  
  path = os.path.dirname(__file__)
  output_file = os.path.join(path, '../visualizations/data/species-metadata.json')
  json_output = json.dumps(env.vdata_json, sort_keys=True, indent=2)
  
  # Output to JSON file
  output = open(output_file, 'w')
  output.write(json_output + "\n")
  output.close()
  # Output to JSONP file
  output = open(output_file + 'p', 'w')
  output.write('%s(%s);\n' % ('species_metadata_callback', json_output))
  output.close()


def vdata_load_csv():
  """
  Load viz data.
  """
  path = os.path.dirname(__file__)
  spfile = os.path.join(path, '../data/species-ids-colors.csv')
  env.csv_file = open(spfile, 'r')
  env.csv_reader = csv.reader(env.csv_file, delimiter=',', quotechar='"', dialect=csv.excel_tab)


def vdata_reset_csv():
  env.csv_file.seek(0)

def vdata_get_csv_value(data_name):
  """
  Load viz data.
  """
  if env.csv_reader <> None:
    vdata_reset_csv()
    
    for row in env.csv_reader:
      if row[0] == data_name:
        return row
  
  # return nothing is did not find
  return None


def vdata_get_thumbs():
  """
  Given sources, creates data for visualization.
  """
  path = os.path.dirname(__file__)
  json_data = {}
  vdata_load_csv()
  
  wp_base = 'http://en.wikipedia.org/wiki/'
  wp_api_base = 'http://en.wikipedia.org/w/api.php?format=json'
  wp_api_title = wp_api_base + '&action=query&prop=images&&imlimit=10&redirects='
  
  # Start creating json object from csv data
  row_count = 0
  for row in env.csv_reader:
    if row_count > 0:
      json_data[row[0]] = {
        'data_name': row[0],
        'site_name': row[1],
        'color': row[2],
        'wp': row[3],
        'wp_thumb': row[4]
      }
      
      api_call = wp_api_base + '&action=query&prop=images|imageinfo|links'
    
    row_count = row_count + 1;
    
        
  # Get wikipedia image URL.  With Wikipedia, the infobox
  # does not have an API really, so use DBPedia instead,
  # but we DBPedia doesn't handle redirects well.
  for sp in json_data:
    this_sp = json_data[sp]
    wp_title = this_sp['wp'][len(wp_base):]
    redirected_title = wp_title
    
    wp_call = wp_api_base + '&action=query&prop=info&inprop=url&intoken=unblock&redirects=&titles=%s' % wp_title
    dbpedia_call = 'http://dbpedia.org/data/%s.json'
    dbpedia_key = 'http://dbpedia.org/resource/%s'
    dbpedia_thumb_key = 'http://dbpedia.org/ontology/thumbnail'
    
    print 'Reading data for %s' % wp_title
    if this_sp['wp_thumb'] <> '':
      print 'Thumb already defined for %s' % wp_title
      continue
    
    # Get redirected title
    wp_json = urllib2.urlopen(wp_call).read()
    wp_results = json.loads(wp_json)
    
    result_count = 0
    for page in wp_results['query']['pages']:
      if result_count == 0:
        redirected_title = wp_results['query']['pages'][page]['fullurl']
        redirected_title = redirected_title[len(wp_base):]
        
      result_count = result_count + 1
    
    # Get data from DBPedia
    dbpedia_call = dbpedia_call % redirected_title
    dbp_json = urllib2.urlopen(dbpedia_call).read()
    dbp_results = json.loads(dbp_json)
    try:
      json_data[sp]['wp_thumb'] = dbp_results[dbpedia_key % redirected_title][dbpedia_thumb_key][0]['value']
    except KeyError:
      print 'KeyError for %s' % wp_title

  # Export to visualization data
  output_file = os.path.join(path, '../visualizations/data/species-metadata.json')
  json_output = json.dumps(json_data, sort_keys=True, indent=2)
  
  # Output to JSON file
  output = open(output_file, 'w')
  output.write(json_output + "\n")
  output.close()
  # Output to JSONP file
  output = open(output_file + 'p', 'w')
  output.write('%s(%s);\n' % ('species_metadata_callback', json_output))
  output.close()


def vdata_get_colors(update=False):
  """
  Read in data from JSON and CSV, put images through ColorSuckr.com.
  Set update to true to only get colors that don't exist yet.
  """
  vdata_load_csv()
  vdata_load_data()
  json_data = env.vdata_json

  # Function to check for existing color
  def check_color(data, color):
    found = False
    for d in data:
      if data[d]['color'] == color:
        found = True
        
    return found
  
  # Get color info from ColorSuckr
  cs_call = 'http://coloursuckr.com/?output=json&img=%s'
  for key in json_data:
    sp = json_data[key]
    
    # Check for color and update
    if (update == True or update == 'True') and sp['color'] <> '':
      print 'Color exists for %s' % key
      continue
    
    print 'Getting colors for %s' % key
    
    # Check for color in CSV
    csv_found = vdata_get_csv_value(key)
    if csv_found <> None and csv_found[2] <> '':
      json_data[key]['color'] = csv_found[2]
      print 'Found color in CSV, #%s' % csv_found[2]
      continue
    
    # Make call
    api_call = cs_call % sp['wp_thumb']
    cs_json = urllib2.urlopen(api_call).read()
    cs_results = json.loads(cs_json)
    
    # Check for existing color and use lightest first
    colors = cs_results[0]['hex']
    counting = 1
    color = colors.pop()
    color = colors.pop()
    
    if color == None or not isinstance(color, basestring):
      print 'Color not found for %s' % key
      print color
      print api_call
      continue
    
    while check_color(json_data, color) == True and counting < len(colors):
      color = colors.pop()
      counting = counting + 1
      
    print 'Found color %s' % color
    json_data[key]['color'] = color
    
  # Save data
  env.vdata_json = json_data
  vdata_save_data()
  


def vdata_tile_colors():
  """
  Read in data from JSON, create colors.mss
  """
  vdata_load_data()
  json_data = env.vdata_json
  
  path = os.path.dirname(__file__)
  spfile = os.path.join(path, './tiles/mn-invasive/colors.mss')
  output = ''
  
  template = """
#invasive[COM_NAME = "%s"][zoom > 0] { marker-fill: #%s }
#invasive[COMMON_NAM = "%s"][zoom > 0] { marker-fill: #%s }
  """
  
  for k in json_data:
    if json_data[k]['color'] <> '':
      output = output + template % (
        json_data[k]['data_name'].replace("'", "\\'"), json_data[k]['color'][0:6], 
        json_data[k]['data_name'].replace("'", "\\'"), json_data[k]['color'][0:6]
      )
  
  # Output to file
  outputf = open(spfile, 'w')
  outputf.write(output + "\n")
  outputf.close()