import ee
import math
from loguru import logger
from dynaconf import settings
from sys import exit

rfNTrees = 500
rfBagFraction = 0.5
rfVarPersplit = 9
pastureMapThreshold = 0.51

indexes = {
    'CAI_L8': "(b('B7') / b('B6'))",
    'CAI_L5_7': "(b('B7') / b('B5'))",
    'NDVI_L8': "(b('B5') - b('B4')) / (b('B5') + b('B4'))",
    'NDWI_L8': "(b('B5') - b('B6')) / (b('B5') + b('B6'))",
    'NDVI_L5_7': "(b('B4') - b('B3')) / (b('B4') + b('B3'))",
    'NDWI_L5_7': "(b('B4') - b('B5')) / (b('B4') + b('B5'))",
    'MASK_L5_7': "(b('QA_PIXEL') == 5440 || b('QA_PIXEL') == 5504) * (b('B4') >= 0)",
    'MASK_L8': "(b('QA_PIXEL') == 21824 || b('QA_PIXEL') == 21952) * (b('B5') >= 0)"
}

landsatBandsWet = ['green_wet', 'red_wet', 'nir_wet', 'swir1_wet', 'swir2_wet', 'ndvi_wet', 'ndwi_wet', 'cai_wet']
landsatBandsWetAmp = ['green_wet_amp', 'red_wet_amp', 'nir_wet_amp', 'swir1_wet_amp', 'swir2_wet_amp', 'ndvi_wet_amp', 'ndwi_wet_amp', 'cai_wet_amp']

def getNeibArea(path, row):

    LANDSAT_GRID = ee.FeatureCollection("users/vieiramesquita/LAPIG-PASTURE/VECTORS/LANDSAT_GRID_V3_PASTURE")

    neitilesT = []
    neitiles = []

    xW = [1, 1]
    yW = [1, 1]

    for pInc in range(int(path) - xW[0], int(path) + xW[1] + 1):
        for rInc in range(int(row) - yW[0], int(row) + yW[1] + 1):
            pAux = pInc
            rAux = rInc

            if int(path) == 1 and pAux == 0:
                pAux = 233
            elif int(path) == 233 and pAux == 234:
                pAux = 1

            Aux = f"{pAux}/{rAux}"
            neitiles.append(Aux)

            rAux_str = f"{rAux:03d}"
            pAux_str = f"{pAux:03d}"

            tAux = f"T{pAux_str}{rAux_str}"
            neitilesT.append(tAux)

    return LANDSAT_GRID.filter(ee.Filter.inList('TILE_T', neitilesT)), neitiles

def clipCollection(img):

    LANDSAT_GRID = ee.FeatureCollection("users/vieiramesquita/LAPIG-PASTURE/VECTORS/LANDSAT_GRID_V3_PASTURE")

    wrs_path_num = ee.Number.parse(img.get('WRS_PATH')).int().format()
    wrs_path = ee.Algorithms.If(
        ee.String(wrs_path_num).length().eq(1),
        ee.String('00').cat(wrs_path_num),
        wrs_path_num
    )

    wrs_row_num = ee.Number.parse(img.get('WRS_ROW')).int().format()
    wrsProps = ee.String(wrs_path).cat('/').cat(wrs_row_num)
    
    gridSelect = LANDSAT_GRID.filter(ee.Filter.eq('SPRNOME', wrsProps))
    return img.clip(gridSelect)


def radians(img):
    return img.toFloat().multiply(math.pi).divide(180)


def temporalFeatures(image):
    min_img = image.reduce(ee.Reducer.min())
    max_img = image.reduce(ee.Reducer.max())
    median_img = image.reduce(ee.Reducer.median())
    stdv_img = image.reduce(ee.Reducer.stdDev())
    percs_img = image.reduce(ee.Reducer.percentile([10, 25, 75, 90]))

    amp_img = image.reduce(ee.Reducer.max()).subtract(image.reduce(ee.Reducer.min())).rename(landsatBandsWetAmp)

    result = ee.Image().select().addBands([min_img, max_img, median_img, amp_img, stdv_img, percs_img])
    return result

def rename_bands(bands_names, suffix):
    def suffixBand(band):
        return ee.String(band).cat(suffix)
    return bands_names.map(suffixBand)


def run_classification(grid, year):

    # Collections
    L8 = ee.ImageCollection("LANDSAT/LC08/C02/T1_TOA")
    L5 = ee.ImageCollection("LANDSAT/LT05/C02/T1_TOA")
    L7 = ee.ImageCollection("LANDSAT/LE07/C02/T1_TOA")

    LANDSAT_GRID = ee.FeatureCollection("users/vieiramesquita/LAPIG-PASTURE/VECTORS/LANDSAT_GRID_V3_PASTURE")

    landsatWRSPath = grid[1:4]
    landsatWRSRow = grid[4:7]

    classificationArea = LANDSAT_GRID.filter(ee.Filter.eq('TILE_T', grid))

    samplingArea, neighborhoodArea = getNeibArea(landsatWRSPath, landsatWRSRow)

    year = ee.Number(year)

    def spectralFeatures(image):
        qaImage_L8 = image.expression(indexes['MASK_L8']).add(image.lte(0))
        qaImage_L57 = image.expression(indexes['MASK_L5_7']).add(image.lte(0))
        qaImage = ee.Image(ee.Algorithms.If(year.gt(2012), qaImage_L8, qaImage_L57))
        
        image_masked = image.updateMask(qaImage)

        ndvi_L8 = image_masked.expression(indexes['NDVI_L8']).select([0], ['NDVI'])
        ndvi_L57 = image_masked.expression(indexes['NDVI_L5_7']).select([0], ['NDVI'])
        ndvi = ee.Image(ee.Algorithms.If(year.gt(2012), ndvi_L8, ndvi_L57))

        ndwi_L8 = image_masked.expression(indexes['NDWI_L8']).select([0], ['NDWI'])
        ndwi_L57 = image_masked.expression(indexes['NDWI_L5_7']).select([0], ['NDWI'])
        ndwi = ee.Image(ee.Algorithms.If(year.gt(2012), ndwi_L8, ndwi_L57))

        cai_L8 = image_masked.expression(indexes['CAI_L8']).select([0], ['CAI'])
        cai_L57 = image_masked.expression(indexes['CAI_L5_7']).select([0], ['CAI'])
        cai = ee.Image(ee.Algorithms.If(year.gt(2012), cai_L8, cai_L57))

        return image_masked.addBands([ndvi, ndwi, cai])

    terrain = ee.Algorithms.Terrain(ee.Image('USGS/SRTMGL1_003'))
    elevation = terrain.select('elevation')
    slope = radians(terrain.select('slope')).expression('b("slope")*100')

    startDate = year.subtract(1).int().format().cat('-07-01')
    endDate = year.add(1).int().format().cat('-06-30')

    landsatCollection = ee.ImageCollection(
        ee.Algorithms.If(
            year.gt(2012), L8, 
            ee.Algorithms.If(ee.List([2000, 2001, 2002, 2012]).contains(year), L7, L5)
        )
    )

    bands = ee.List(ee.Algorithms.If(
        year.gt(2012), 
        ["B3", "B4", "B5", "B6", "B7", "NDVI", "NDWI", "CAI"], 
        ["B2", "B3", "B4", "B5", "B7", "NDVI", "NDWI", "CAI"]
    ))

    neibData = ee.List([])
    
    for scene in neighborhoodArea:
        sceneInfo = scene.split('/')
        
        spectralDataNei = landsatCollection \
            .filterMetadata('WRS_PATH', 'equals', int(sceneInfo[0])) \
            .filterMetadata('WRS_ROW', 'equals', int(sceneInfo[1])) \
            .filterDate(startDate, endDate) \
            .map(spectralFeatures) \
            .map(clipCollection) \
            .select(bands)
            
        wetThresholdNei = spectralDataNei.select("NDVI").reduce(ee.Reducer.percentile([25]))
        
        def onlyWetSeasonNei(img):
            seasonMask = img.select("ndvi_wet").gte(wetThresholdNei)
            return img.updateMask(seasonMask)
            
        wetSpectralDataNei = spectralDataNei.select(bands, landsatBandsWet).map(onlyWetSeasonNei)
        
        temporalData = temporalFeatures(wetSpectralDataNei).addBands([elevation, slope])
        bandSize = ee.Number(temporalData.bandNames().size())
        
        temporalData = temporalData.set('BandNumber', bandSize)
        neibData = neibData.add(temporalData)
        
    neibCollection = ee.ImageCollection(neibData).filter(ee.Filter.gt('BandNumber', 2)).mosaic()

    original_classFieldName = ee.String('cons_').cat(year.int().format())
    classFieldName = ee.String(ee.Algorithms.If(
        year.gt(2022), 'cons_2022', 
        ee.Algorithms.If(year.lt(1985), 'cons_1985', original_classFieldName)
    ))

    trainSamples_main = ee.FeatureCollection('users/vieiramesquita/LAPIG-PASTURE/VECTORS/mapa_pastagem_col8_50k_final_v2') \
        .select([classFieldName])

    extra_samples = (ee.FeatureCollection('users/vieiramesquita/LAPIG-PASTURE/VECTORS/Pasture_Extra_Brasil_plus_Date_v1_6')
        .filter(ee.Filter.lte('YearPastur', year)))

    def make_classFieldName(feat):
        return feat.set(classFieldName, feat.get('is_pasture'))

    reclass_extra_samples = extra_samples.map(make_classFieldName).select([classFieldName])

    classFieldName_mosaic = ee.String(ee.Algorithms.If(
        year.gt(2024), 'cons_2024', 
        ee.Algorithms.If(year.lt(1985), 'cons_1985', original_classFieldName)
    ))

    extra_mosaic = ee.FeatureCollection('users/vieiramesquita/LAPIG-PASTURE/VECTORS/pasture_extra_mapbiomas_col10_mosaicos_pastagem') \
        .select([classFieldName_mosaic], [classFieldName])

    trainSamples = trainSamples_main.filterBounds(samplingArea) \
        .merge(reclass_extra_samples.filterBounds(samplingArea)) \
        .merge(extra_mosaic.filterBounds(samplingArea))

    classifier = ee.Classifier.smileRandomForest(
        numberOfTrees=rfNTrees,
        variablesPerSplit=rfVarPersplit,
        bagFraction=rfBagFraction,
        seed=year
    ).setOutputMode('PROBABILITY')

    trainSamplesFeeded = neibCollection.sampleRegions(
        collection=trainSamples.filter(ee.Filter.neq(classFieldName, None)),
        properties=[classFieldName],
        scale=30,
        tileScale=16
    )

    classifier = classifier.train(trainSamplesFeeded, classFieldName)

    classification = ee.Image(neibCollection).classify(classifier).select(0)\
            .rename(ee.String('CY')\
            .cat(year.int().format()))

    image = classification.clip(classificationArea).multiply(10000).toInt()

    return classificationArea.geometry().bounds(), image

def submit_task(task_config):
    grid, year = task_config["grid"], task_config["year"]
    ROI, image = run_classification(grid, year)

    landsatWRSPath = grid[1:4]
    landsatWRSRow = grid[4:7]
    outname = f"br_pasture_lapig_col10_v4_{landsatWRSPath}_{landsatWRSRow}_Y{year}"
    
    # task = ee.batch.Export.image.toCloudStorage(
    #     image=image,
    #     description=outname,
    #     bucket="mapbiomas-public-temp",
    #     fileNamePrefix=f"COLECAO/LANDSAT/PASTURE/C10_v4/{outname}",
    #     region=ROI,
    #     scale=30,
    #     maxPixels=1e13,
    #     crs="EPSG:4326"
    # )

    task = ee.batch.Export.image.toDrive(
        image=image, description=outname, 
        fileNamePrefix=f"mapbiomas_pasture_c11_v1/{outname}",
        folder="MAPBIOMAS_TEST_PASTURE",
        region=ROI, scale=30, maxPixels=1e13, crs="EPSG:4326"
    )

    task.start()
    return {"name": outname, "gee_id": task.id, "config": task_config, "retries": 0}