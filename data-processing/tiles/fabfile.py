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
env.pg_host = 'localhost'
env.pg_dbname = 'minnpost_fec'
env.pg_user = 'postgres'
env.pg_pass = ''
env.labels = None
env.tile_scheme = 'xyz'
env.tile_template = '{z}/{x}/{y}'
env.bounds = None
env.bbox = None

# Tilemill paths.  For Ubuntu
if os.path.exists('/usr/share/tilemill'):
  env.tilemill_path = '/usr/share/tilemill'
  env.tilemill_projects = '/usr/share/mapbox/project'
  env.node_path = '/usr/bin/node'
  env.os = 'Ubuntu'
# OSX
else:
  env.tilemill_path = '/Applications/TileMill.app/Contents/Resources'
  env.tilemill_projects = '~/Documents/MapBox/project'
  env.node_path = '%(tilemill_path)s/node' % env
  env.os = 'OSX'
  
"""
Environments
"""
def production():
  """
  Work on production environment
  """
  env.settings = 'production'
  #env.s3_buckets = ['a.tiles.minnpost', 'b.tiles.minnpost', 'c.tiles.minnpost', 'd.tiles.minnpost']
  env.s3_buckets = ['a.tiles.minnpost']
  env.acl = 'acl-public'
  env.base_tiles_grids = [
    'http://a.tiles.minnpost.com',
    'http://b.tiles.minnpost.com',
    'http://c.tiles.minnpost.com',
    'http://d.tiles.minnpost.com'
  ]


def staging():
  """
  Work on staging environment
  """
  env.settings = 'staging'
  env.s3_buckets = ['testing.tiles.minnpost']
  env.acl = 'acl-public'
  env.base_tiles_grids = [
    'http://testing.tiles.minnpost.s3.amazonaws.com'
  ]
  

def map(name):
  """
  Select map to work on.
  """
  env.map = name
  

def tile_scheme(scheme='xyz'):
  """
  Change tilescheme.
  """
  env.tile_scheme = scheme
  

def bbox(b1=None, b2=None, b3=None, b4=None):
  """
  Change bounding box.
  """
  if b1 != None and b2 != None and b3 != None and b4 != None:
    env.bounds = [float(b1), float(b2), float(b3), float(b4)]
    env.bbox = '%s,%s,%s,%s' % (b1, b2, b3, b4)
  

def deploy_to_s3(concurrency):
  """
  Deploy tiles to S3.
  """
  require('settings', provided_by=[production, staging])
  require('map', provided_by=[map])
  env.concurrency = concurrency
  _create_map_suffix()

  # Deploy to many buckets (multi-dns-head mode)
  for bucket in env.s3_buckets:
    env.s3_bucket = bucket    
    local('ivs3 %(map)s/tiles %(s3_bucket)s/%(project_name)s/%(map)s%(map_suffix)s --%(acl)s -c %(concurrency)s' % env)


def export_deploy(concurrency=32, minzoom=None, maxzoom=None):
  """
  Deploy a map. Optionally takes a concurrency parameter indicating how many files to upload simultaneously.
  """
  require('settings', provided_by=[production, staging])
  require('map', provided_by=[map])
  
  create_exports()
  cleanup_exports()
  generate_mbtile(minzoom, maxzoom)
  generate_tiles_from_mbtile()
  generate_tilejson()
  deploy_to_s3(concurrency)
  reset_labels()
  
  
def deploy_tilejson(concurrency=32, minzoom=None, maxzoom=None):
  """
  Deploy just the tilejson export. Optionally takes a concurrency parameter indicating how many files to upload simultaneously.
  """
  require('settings', provided_by=[production, staging])
  require('map', provided_by=[map])
  
  create_exports()
  cleanup_exports()
  generate_tilejson()
  deploy_to_s3(concurrency)
  reset_labels()
  

def link_caches():
  """
  Link local map cache to Mapbox cache to speed up mapnik conversion.
  """
  require('map', provided_by=[map])
  
  env.base_path = os.getcwd()
  exists = os.path.exists('%(base_path)s/%(map)s/cache' % env)
  if exists:
    print "There already a linked cache directory."
  else:
    env.tilemill_cache = os.path.expanduser('%(tilemill_projects)s/../cache/' % env)
    local(('ln -s %(tilemill_cache)s %(base_path)s/%(map)s/cache') % env)
  

def carto_to_mapnik():
  """
  Convert carto styles to mapnik configuration.  This should be able to
  be done with the Tilemill export API.
  """
  require('map', provided_by=[map])
  link_caches()
  local('%(tilemill_path)s/node_modules/carto/bin/carto %(map)s/project.mml > %(map)s/%(map)s.xml' % env)
  

def generate_mbtile(minzoom=None, maxzoom=None):
  """
  Generate MBtile.
  """
  require('map', provided_by=[map])
  
  # Read data from project mml
  with open('%(map)s/project.mml' % env, 'r') as f:
    config = json.load(f)
  
    # Define config values
    env.minzoom = config['minzoom'] if minzoom == None else minzoom
    env.maxzoom = config['maxzoom'] if maxzoom == None else maxzoom
    
    # If env bbox has not been set, then use config
    if env.bbox == None:
      env.bbox = '%f,%f,%f,%f' % (config['bounds'][0], config['bounds'][1], config['bounds'][2], config['bounds'][3])
    
    # Workaround for ICU
    if env.os == 'OSX':
      local('export ICU_DATA=%(tilemill_path)s/data/icu/' % env)
    
    # Export
    local('%(tilemill_path)s/node %(tilemill_path)s/index.js export --format=mbtiles --minzoom=%(minzoom)s --maxzoom=%(maxzoom)s --bbox=%(bbox)s %(map)s %(map)s/exports/%(map)s.mbtiles' % env)


def generate_tiles_from_mbtile():
  """
  Generate MBtile.
  """
  require('map', provided_by=[map])
  read_project()
    
  exists = os.path.exists('%(map)s/exports/%(map)s.mbtiles' % env)
  if exists:
    with settings(warn_only=True):
      # MB-Util uses 'osm' as the scheme name
      env.mb_utl_scheme = env.tile_scheme
      if env.tile_scheme == 'xyz':
        env.mb_utl_scheme = 'osm'
    
      local('rm -rf %(map)s/tiles-tmp' % env)
      local('rm -rf %(map)s/tiles' % env)
      local('mb-util --scheme=%(mb_utl_scheme)s %(map)s/exports/%(map)s.mbtiles %(map)s/tiles-tmp' % env)
      local('mv "%(map)s/tiles-tmp/%(map_version)s/%(map_title)s" %(map)s/tiles' % env)
      local('mv %(map)s/tiles-tmp/metadata.json %(map)s/tiles/metadata.json' % env)
  else:
    print 'No MBTile file found in exports.'


def generate_tilejson():
  """
  Generate valid tilejson file.  This should be able to be accomplished
  with the api, such as http://localhost:20009/api/Project/:id
  """
  require('settings', provided_by=[production, staging])
  require('map', provided_by=[map])
  _create_map_suffix()
  
  # Utilize project data
  response = urllib2.urlopen('http://localhost:20009/api/Project/%(map)s' % env)
  config = json.load(response)
  if config:
    tilejson = config
    
    # Force scheme as tilemill always like xyz and maybe we dont
    tilejson['scheme'] = env.tile_scheme
    
    # Attempt to get values from config
    try:
      tilejson['version'] = config['version'] if config.has_key('version') else '1.0.0'
      tilejson['bounds'] = config['bounds'] if config.has_key('bounds') else [-180, -90, 180, 90]
    except KeyError:
      print 'Key error'
    
    # Figure out templates
    tilejson['grids'] = []
    tilejson['tiles'] = []
    for bucket in env.base_tiles_grids:
      env.this_bucket = bucket 
      tilejson['grids'].append('%(this_bucket)s/%(project_name)s/%(map)s%(map_suffix)s/%(tile_template)s.grid.json' % env)
      tilejson['tiles'].append('%(this_bucket)s/%(project_name)s/%(map)s%(map_suffix)s/%(tile_template)s.png' % env)
    
    # Write regular and jsonp tilejson files
    tilejson_file = open('%(map)s/tiles/tilejson.json' % env, 'w')
    tilejson_file.write(json.dumps(tilejson, sort_keys = True, indent = 2))
    tilejson_file.close()
    tilejsonp_file = open('%(map)s/tiles/tilejson.jsonp' % env, 'w')
    tilejsonp_file.write('grid(%s);' % json.dumps(tilejson, sort_keys = True, indent = 2))
    tilejsonp_file.close()


def generate_tiles_mapnik(process_count, minzoom=None, maxzoom=None):
  """
  Render tile from mapnik configuration
  """
  env.process_count = process_count

  # Read data from project mml
  with open('%(map)s/project.mml' % env, 'r') as f:
    config = json.load(f)
  
    # Define config values
    env.minzoom = config['minzoom'] if minzoom == None else minzoom
    env.maxzoom = config['maxzoom'] if maxzoom == None else maxzoom
    env.minlon = config['bounds'][0]
    env.minlat = config['bounds'][1]
    env.maxlon = config['bounds'][2]
    env.maxlat = config['bounds'][3]

    # Cleanup tiles
    local('rm -rf %(map)s/tiles/*' % env)
    
    # Render tiles
    command = 'ivtile %(map)s/%(map)s.xml %(map)s/tiles %(maxlat)s %(minlon)s %(minlat)s %(maxlon)s %(minzoom)s %(maxzoom)s -p %(process_count)s'
    if 'buffer' in env:
      command += ' -b %(buffer)s'
    local(command % env)
  

def no_labels():
  """
  Updates tilemill project to no use labels
  """
  require('map', provided_by=[map])
  env.labels = False
  
  # Create a backup
  exists = os.path.exists('%(map)s/project.mml.orig' % env)
  if exists != True:
    local('cp %(map)s/project.mml %(map)s/project.mml.orig' % env);
  
  # From the original, load the json, find any label style
  # and remove.
  overwrite = open('%(map)s/project.mml' % env, 'w')
  with open('%(map)s/project.mml.orig' % env, 'r') as f:
    mml = json.load(f)
    
    # Process styles
    styles = []
    for index, item in enumerate(mml['Stylesheet']):
      if item != 'labels.mss':
        styles.append(item)
    mml['Stylesheet'] = styles
    
    overwrite.write(json.dumps(mml, sort_keys = True, indent = 2))
    overwrite.close()
  

def only_labels():
  """
  Updates tilemill project to use only labels
  """
  require('map', provided_by=[map])
  env.labels = True
  
  # Create a backup
  exists = os.path.exists('%(map)s/project.mml.orig' % env)
  if exists != True:
    local('cp %(map)s/project.mml %(map)s/project.mml.orig' % env);
  
  # From the original, load the json, keep palette and labels
  overwrite = open('%(map)s/project.mml' % env, 'w')
  with open('%(map)s/project.mml.orig' % env, 'r') as f:
    mml = json.load(f)
    
    # Process styles
    styles = []
    for index, item in enumerate(mml['Stylesheet']):
      if item == 'labels.mss' or item == 'palette.mss':
        styles.append(item)
    mml['Stylesheet'] = styles
    
    overwrite.write(json.dumps(mml, sort_keys = True, indent = 2))
    overwrite.close()
  

def reset_labels():
  """
  Resets any label changes process
  """
  require('map', provided_by=[map])
  
  # Check for orig
  exists = os.path.exists('%(map)s/project.mml.orig' % env)
  if exists:
    local('rm -f %(map)s/project.mml' % env);
    local('mv %(map)s/project.mml.orig %(map)s/project.mml' % env);
  else:
    print 'No label processing to reset.'
  

def _create_map_suffix():
  """
  Creates map suffix for deploying
  """
  if env.labels == None:
    env.map_suffix = ''
  if env.labels == True:
    env.map_suffix = '-labels'
  if env.labels == False:
    env.map_suffix = '-no-labels'


def read_project():
  """
  Get data from the TileMill project, to be used in other
  commands.
  """
  require('map', provided_by=[map])

  # Read JSON from file
  with open('%(map)s/project.mml' % env, 'r') as f:
    mml = json.load(f)
    env.map_title = mml['name']
    
    # Version is not always defined
    try:
      env.map_version = mml['version']
    except KeyError:
      env.map_version = '1.0.0'

def create_exports():
  """
  Create export directories
  """
  require('map', provided_by=[map])
  local('mkdir -p %(map)s/tiles' % env)
  local('mkdir -p %(map)s/exports' % env)
  

def cleanup_exports():
  """
  Cleanup export directories
  """
  require('map', provided_by=[map])
  local('rm -rf %(map)s/tiles-tmp' % env)
  local('rm -rf %(map)s/tiles/*' % env)
  local('rm -rf %(map)s/exports/*' % env)


def link():
  """
  Link a map into the MapBox directory
  """
  require('map', provided_by=[map])
  
  exists = os.path.exists(os.path.expanduser('%(tilemill_projects)s/%(map)s' % env))
  if exists:
    print "A directory with that name already exists in your MapBox projects."
  else:
    env.base_path = os.getcwd()
    local(('ln -s %(base_path)s/%(map)s/ %(tilemill_projects)s/%(map)s') % env)


def unlink():
  """
  unLink a map into the MapBox directory
  """
  require('map', provided_by=[map])
  
  exists = os.path.exists(os.path.expanduser('%(tilemill_projects)s/%(map)s' % env))
  if exists:
    local(('unlink %(tilemill_projects)s/%(map)s') % env)
  else:
    print "There is no directpry with that name in your MapBox projects."
  

def clone(name):
  """
  Clone a map to work on.
  """
  require('map', provided_by=[map])
  env.clone = name
  
  exists = os.path.exists('%(clone)s' % env)
  if exists:
    print "A directory with that name already exists in this project."
  else:
    local('cp -r %(map)s %(clone)s' % env)
    
    # Now link it
    env.map = env.clone
    link()


def remove_from_s3():
  """
  Remove map from S3
  """
  require('settings', provided_by=[production, staging])
  require('map', provided_by=[map])
  
  with settings(warn_only=True):
    for bucket in env.s3_buckets:
      env.s3_bucket = bucket 
      local('s3cmd del --recursive s3://%(s3_bucket)s/%(project_name)s/%(map)s' % env)


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


def vdata_get_thumbs():
  """
  Given sources, creates data for visualization.
  """
  path = os.path.dirname(__file__)
  json_data = {}
  wp_base = 'http://en.wikipedia.org/wiki/'
  wp_api_base = 'http://en.wikipedia.org/w/api.php?format=json'
  wp_api_title = wp_api_base + '&action=query&prop=images&&imlimit=10&redirects='
  
  # Read CSV data
  spfile = os.path.join(path, '../data/species-ids-colors.csv')
  reader = csv.reader(open(spfile, 'rU'), delimiter=',', quotechar='"', dialect=csv.excel_tab)
  
  row_count = 0
  for row in reader:
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


def vdata_get_colors():
  """
  Read in data from JSON, put images through ColorSuckr.com
  """
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
    print 'Getting colors for %s' % key
    
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
#invasive[COM_NAME = "%s"] { marker-fill: #%s }
#invasive[COMMON_NAM = "%s"] { marker-fill: #%s }
  """
  
  for k in json_data:
    if json_data[k]['color'] <> '':
      output = output + template % (
        json_data[k]['data_name'].replace("'", "\'"), json_data[k]['color'][0:6], 
        json_data[k]['data_name'].replace("'", "\'"), json_data[k]['color'][0:6]
      )
  
  # Output to file
  outputf = open(spfile, 'w')
  outputf.write(output + "\n")
  outputf.close()