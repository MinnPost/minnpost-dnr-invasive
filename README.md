# Minnesota Invasive Species Map

Map of [invasive species in Minnesota](http://www.dnr.state.mn.us/invasives/index.html).

## Data

Data from the Minnesota DNR and their awesome [Data Deli](http://deli.dnr.state.mn.us/):

* Invasive Species - Aquatic Observations
    * http://deli.dnr.state.mn.us/metadata.html?id=L390007760203
    * ftp://ftp.dnr.state.mn.us/pub/deli/d24157283106212.zip
* Invasive Species - Terrestrial Observations
    * http://deli.dnr.state.mn.us/metadata.html?id=L390004820203
    * ftp://ftp.dnr.state.mn.us/pub/deli/d23954283106172.zip
* Combined Shapefile
    * https://s3.amazonaws.com/data.minnpost/geospatial-data/dnr-data-deli/20120613-combined-DNR+Invasive+Species.zip
* Data from the DNR site concerning invasive species.
    * https://scraperwiki.com/scrapers/mn_dnr_invasive_species/

## Data processing

* To work on the TileMill project: ```cd data-processing/tiles && fab map:mn-invasive link; cd -;```
* In order to get the shapefile into a PostGIS database to do some basic analysis, you can utilize ogr2ogr: ```ogr2ogr -f "PostgreSQL" PG:"host=localhost user=postgres dbname=minnpost" 20120613-combined-DNR\ Invasive\ Species.shp```
* Create species metadata:
    * Generate thumbs from CSV, Wikipedia, and DBPedia: ```cd data-processing && fab vdata_get_thumbs; cd -;```
    * Get colors from [ColorSuckr](http://coloursuckr.com/): ```cd data-processing && fab vdata_get_colors:True; cd -;```
    * Put colors into TileMill project: ```cd data-processing && fab vdata_tile_colors; cd -;```
    * Get extra DNR data via Scraper Wiki: ```cd data-processing && fab vdata_get_dnr_data; cd -;```
* Export tiles to S3: ```cd data-processing/tiles && fab map:mn-invasive production export_deploy:32,4,5; cd -;```