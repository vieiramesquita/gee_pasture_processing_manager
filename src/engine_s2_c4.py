import ee
import math
from loguru import logger
from dynaconf import settings
from sys import exit

rfNTrees = 500 #Number of random trees;
rfBagFraction = 0.5 #Fraction (10^-2%) of variables in the bag;
rfVarPersplit = 13 #Number of varibales per tree branch;

indexes = {
 'CAI':    "(b('B12') / b('B11'))",
 'NDVI':   "(b('B8') - b('B4')) / (b('B8') + b('B4'))",
 'NDWI':   "(b('B8A') - b('B11')) / (b('B8A') + b('B11'))",
 'CRI1': "1/(b('B2')) - 1/(b('B3'))",
 'ARI_1': "(1/b('B3') - 1/b('B6'))*1000",
 'RGR': "b('B4')/b('B3')",
 'PSRI': "(b('B4') - b('B3') )/(b('B6'))",
 'SATVI': "((b('B11') - b('B4'))/(b('B11') + b('B4') + 0.5))*(1*0.5)-(b('B12')/2)*0.0001"
}

def spectralFeatures(image):
  ndvi  = image.expression(indexes["NDVI"]).select([0],['NDVI'])
  ndwi  = image.expression(indexes["NDWI"]).select([0],['NDWI'])
  cai   = image.expression(indexes["CAI"]).select([0],['CAI'])
  cri1  = image.expression(indexes["CRI1"]).select([0],['CRI1'])
  ari1  = image.expression(indexes["ARI_1"]).select([0],['ARI_1'])
  rgr   = image.expression(indexes["RGR"]).select([0],['RGR'])
  psri  = image.expression(indexes["PSRI"]).select([0],['PSRI'])
  satvi = image.expression(indexes["SATVI"]).select([0],['SATVI'])
  image = image.addBands([ndvi,ndwi,cai,cri1,ari1,rgr,psri,satvi])
  return image

def temporalFeatures(image):
  min = image.reduce(ee.Reducer.min())
  max = image.reduce(ee.Reducer.max())
  median = image.reduce(ee.Reducer.median())
  stdv = image.reduce(ee.Reducer.stdDev())
  amp = (image.reduce(ee.Reducer.max()).subtract(image.reduce(ee.Reducer.min())).rename(BandsWetAmp))
  result = (ee.Image().select().addBands([min,max,median,amp,stdv]))
  return result

def temporalPercs(image):
  percs = image.reduce(ee.Reducer.percentile([10,25,75,90]))
  result = ee.Image().select().addBands([percs])
  return result

def rename_bands(bands_names,suffix):
  def suffixBand(band):
    return ee.String(band).cat(suffix)
  return bands_names.map(suffixBand)

def maskClouds(img):
  mask = img.select('cs').gte(0.5);
  return img.updateMask(mask);

def radians(img):
 return img.toFloat().multiply(math.pi).divide(180)

def res_bilinear(img):
  bands = img.select('B5','B6','B7','B8A','B11','B12');
  return img.resample('bilinear').reproject(**{
    'crs': bands.projection().crs(),
    'scale': img.select('B8').projection().nominalScale()
  })
  
def maskEdges(s2_img):
  return s2_img.updateMask(
    s2_img.select('B8A').mask().updateMask(s2_img.select('B9').mask()))


BandsWet = ['blue_wet','green_wet','red_wet','rededge1_wet','rededge2_wet','rededge3_wet',
'nir_wet','rededge4_wet' ,'swir1_wet','swir2_wet','ndvi_wet','ndwi_wet','cai_wet',
'cri1_wet', 'ari1_wet', 'rgr_wet', 'psri_wet', 'satvi_wet'];

BandsWetAmp = ['blue_wet_amp','green_wet_amp','red_wet_amp','rededge1_wet_amp',
'rededge2_wet_amp','rededge3_wet_amp','nir_wet_amp','rededge4_wet_amp','swir1_wet_amp','swir2_wet_amp',
'ndvi_wet_amp','ndwi_wet_amp','cai_wet_amp','cri1_wet_amp', 'ari1_wet_amp', 'rgr_wet_amp',
'psri_wet_amp', 'satvi_wet_amp'];

def run_classification(carta, year):
  cartas = ee.FeatureCollection("users/vieiramesquita/LAPIG-PASTURE/VECTORS/CARTAS_IBGE_BR_mod")
  terrain = ee.Algorithms.Terrain(ee.Image("NASA/NASADEM_HGT/001"));
  elevation = terrain.select('elevation');
  slope = (radians(terrain.select('slope'))).expression('b("slope")*100');

  nm_carta = carta
  
  cartas_area = cartas.filter(ee.Filter.eq('grid_name',nm_carta))
  cartas_buffer = cartas_area.geometry().buffer(100000)

  START_DATE = ee.Date(str(year-1)+'-07-01');
  END_DATE = ee.Date(str(year+1)+'-06-30');
  
  s2 = (ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
    .filterBounds(cartas_buffer)
    .filterDate(START_DATE,END_DATE))

  csPlus = (ee.ImageCollection('GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED')
    .filterBounds(cartas_buffer)
    .filterDate(START_DATE,END_DATE))

  csPlusBands = csPlus.first().bandNames();
  
  s2CloudMasked = (s2.linkCollection(csPlus, csPlusBands)
                    .filter(ee.Filter.lte('CLOUDY_PIXEL_PERCENTAGE',80))
                    .map(maskEdges)
                    .map(maskClouds)
                    .map(res_bilinear))
  
  spectralDataNei = (s2CloudMasked
                     .map(spectralFeatures)
                     .select(['B2','B3','B4','B5','B6','B7','B8','B8A',
                     'B11','B12','NDVI','NDWI','CAI','CRI1', 'ARI_1', 'RGR',
                     'PSRI', 'SATVI']))
  
  wetThresholdNei = (spectralDataNei
                           .select("NDVI")
                           .reduce(ee.Reducer.percentile([15])))
  
  def onlyWetSeasonNei(image):
    seasonMask = image.select("ndvi_wet").gte(wetThresholdNei)
    return image.mask(seasonMask)
                           
  wetSpectralDataNei = (spectralDataNei
                           .select(spectralDataNei.first().bandNames(), BandsWet)
                           .map(onlyWetSeasonNei))
                       
  temporalData = (temporalPercs(wetSpectralDataNei)).addBands([temporalFeatures(wetSpectralDataNei), elevation, slope])
     
  featureSpace = ee.Image(temporalData)
  
  classFieldName = f'cons_{year}'

  # Load main training samples
  trainSamples_main = ee.FeatureCollection('users/vieiramesquita/LAPIG-PASTURE/VECTORS/mapa_pastagem_col8_50k_final_v2')

  if year > 2022:
      classFieldName = 'cons_2022'
  elif year < 1985:
      classFieldName = 'cons_1985' 
  else:
      classFieldName = classFieldName
  
  trainSamples_main = trainSamples_main.select([classFieldName]);

  extra_samples = (ee.FeatureCollection('users/vieiramesquita/LAPIG-PASTURE/VECTORS/Pasture_Extra_Brasil_plus_Date_v1_6')
    .filter(ee.Filter.lte('YearPastur', year)));
  
  def make_classFieldName(feat):
    return feat.set(classFieldName,feat.get('is_pasture'))
  
  reclass_extra_samples = extra_samples.map(make_classFieldName).select([classFieldName]);

  if year > 2024:
      classFieldName_mosaic = 'cons_2024'
  elif year < 1985:
      classFieldName_mosaic = 'cons_1985' 
  else:
      classFieldName_mosaic = classFieldName

  extra_mosaic = ee.FeatureCollection('users/vieiramesquita/LAPIG-PASTURE/VECTORS/pasture_extra_mapbiomas_col10_mosaicos_pastagem')
  extra_mosaic = extra_mosaic.select([classFieldName_mosaic],[classFieldName])

  trainSamples = (trainSamples_main
    .filterBounds(cartas_buffer)
    .merge(reclass_extra_samples.filterBounds(cartas_buffer))
    .merge(extra_mosaic.filterBounds(cartas_buffer)));

  classifier = ee.Classifier.smileRandomForest(rfNTrees, rfVarPersplit, 1, rfBagFraction, None, year);
  classifier = classifier.setOutputMode('PROBABILITY');
  
  trainSamplesFeeded = (featureSpace.sampleRegions(**{
    'collection': trainSamples.filterBounds(cartas_buffer).filter(ee.Filter.neq(classFieldName,None)),
    'properties': [classFieldName],
    'scale': 10,
    'tileScale': 16
  }))

  classifier = classifier.train(trainSamplesFeeded, classFieldName);
  classification = featureSpace.classify(classifier).select(0);

  return (
        cartas_area.geometry().bounds(),
        ee.Image(classification).multiply(10000).int16().clip(cartas_area),
  )

def submit_task(task_config):
    year, carta = task_config["year"], task_config["carta"]
    ROI, image = run_classification(carta, year)
    description = f"{carta}_{year}"

    task = ee.batch.Export.image.toDrive(
        image=image, description=description, 
        fileNamePrefix=f"COLECAO/PASTURE/{description}",
        folder="MAPBIOMAS_TEST_PASTURE",
        region=ROI, scale=10, maxPixels=1e13, crs="EPSG:4326"
    )

    task.start()
    return {"name": description, "gee_id": task.id, "config": task_config, "retries": 0}
