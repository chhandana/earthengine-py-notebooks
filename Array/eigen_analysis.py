# %%
"""
<table class="ee-notebook-buttons" align="left">
    <td><a target="_blank"  href="https://github.com/giswqs/earthengine-py-notebooks/tree/master/Array/eigen_analysis.ipynb"><img width=32px src="https://www.tensorflow.org/images/GitHub-Mark-32px.png" /> View source on GitHub</a></td>
    <td><a target="_blank"  href="https://nbviewer.jupyter.org/github/giswqs/earthengine-py-notebooks/blob/master/Array/eigen_analysis.ipynb"><img width=26px src="https://upload.wikimedia.org/wikipedia/commons/thumb/3/38/Jupyter_logo.svg/883px-Jupyter_logo.svg.png" />Notebook Viewer</a></td>
    <td><a target="_blank"  href="https://mybinder.org/v2/gh/giswqs/earthengine-py-notebooks/master?filepath=Array/eigen_analysis.ipynb"><img width=58px src="https://mybinder.org/static/images/logo_social.png" />Run in binder</a></td>
    <td><a target="_blank"  href="https://colab.research.google.com/github/giswqs/earthengine-py-notebooks/blob/master/Array/eigen_analysis.ipynb"><img src="https://www.tensorflow.org/images/colab_logo_32px.png" /> Run in Google Colab</a></td>
</table>
"""

# %%
"""
## Install Earth Engine API and geemap
Install the [Earth Engine Python API](https://developers.google.com/earth-engine/python_install) and [geemap](https://github.com/giswqs/geemap). The **geemap** Python package is built upon the [ipyleaflet](https://github.com/jupyter-widgets/ipyleaflet) and [folium](https://github.com/python-visualization/folium) packages and implements several methods for interacting with Earth Engine data layers, such as `Map.addLayer()`, `Map.setCenter()`, and `Map.centerObject()`.
The following script checks if the geemap package has been installed. If not, it will install geemap, which automatically installs its [dependencies](https://github.com/giswqs/geemap#dependencies), including earthengine-api, folium, and ipyleaflet.

**Important note**: A key difference between folium and ipyleaflet is that ipyleaflet is built upon ipywidgets and allows bidirectional communication between the front-end and the backend enabling the use of the map to capture user input, while folium is meant for displaying static data only ([source](https://blog.jupyter.org/interactive-gis-in-jupyter-with-ipyleaflet-52f9657fa7a)). Note that [Google Colab](https://colab.research.google.com/) currently does not support ipyleaflet ([source](https://github.com/googlecolab/colabtools/issues/60#issuecomment-596225619)). Therefore, if you are using geemap with Google Colab, you should use [`import geemap.eefolium`](https://github.com/giswqs/geemap/blob/master/geemap/eefolium.py). If you are using geemap with [binder](https://mybinder.org/) or a local Jupyter notebook server, you can use [`import geemap`](https://github.com/giswqs/geemap/blob/master/geemap/geemap.py), which provides more functionalities for capturing user input (e.g., mouse-clicking and moving).
"""

# %%
# Installs geemap package
import subprocess

try:
    import geemap
except ImportError:
    print('geemap package not installed. Installing ...')
    subprocess.check_call(["python", '-m', 'pip', 'install', 'geemap'])

# Checks whether this notebook is running on Google Colab
try:
    import google.colab
    import geemap.eefolium as emap
except:
    import geemap as emap

# Authenticates and initializes Earth Engine
import ee

try:
    ee.Initialize()
except Exception as e:
    ee.Authenticate()
    ee.Initialize()  

# %%
"""
## Create an interactive map 
The default basemap is `Google Satellite`. [Additional basemaps](https://github.com/giswqs/geemap/blob/master/geemap/geemap.py#L13) can be added using the `Map.add_basemap()` function. 
"""

# %%
Map = emap.Map(center=[40,-100], zoom=4)
Map.add_basemap('ROADMAP') # Add Google Map
Map

# %%
"""
## Add Earth Engine Python script 
"""

# %%
# Add Earth Engine dataset
# Compute the Principal Components of a Landsat 8 image.


# Load a landsat 8 image, select the bands of interest.
image = ee.Image('LANDSAT/LC8_L1T/LC80440342014077LGN00') \
  .select(['B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B10', 'B11'])

# Display the input imagery and the region in which to do the PCA.
region = image.geometry()
Map.centerObject(ee.FeatureCollection(region), 10)
Map.addLayer(ee.Image().paint(region, 0, 2), {}, 'Region')
Map.addLayer(image, {'bands': ['B5', 'B4', 'B2'], 'min': 0, 'max': 20000}, 'Original Image')

# Set some information about the input to be used later.
scale = 30
bandNames = image.bandNames()

# Mean center the data to enable a faster covariance reducer
# and an SD stretch of the principal components.
meanDict = image.reduceRegion(**{
    'reducer': ee.Reducer.mean(),
    'geometry': region,
    'scale': scale,
    'maxPixels': 1e9
})
means = ee.Image.constant(meanDict.values(bandNames))
centered = image.subtract(means)

# This helper function returns a list of new band names.
def getNewBandNames(prefix):
  seq = ee.List.sequence(1, bandNames.length())
  return seq.map(lambda b: ee.String(prefix).cat(ee.Number(b).int().format()))


# This function accepts mean centered imagery, a scale and
# a region in which to perform the analysis.  It returns the
# Principal Components (PC) in the region as a new image.
def getPrincipalComponents(centered, scale, region):
  # Collapse the bands of the image into a 1D array per pixel.
  arrays = centered.toArray()

  # Compute the covariance of the bands within the region.
  covar= arrays.reduceRegion(**{
    'reducer': ee.Reducer.centeredCovariance(),
    'geometry': region,
    'scale': scale,
    'maxPixels': 1e9
  })

  # Get the 'array' covariance result and cast to an array.
  # This represents the band-to-band covariance within the region.
  covarArray = ee.Array(covar.get('array'))

  # Perform an eigen analysis and slice apart the values and vectors.
  eigens = covarArray.eigen()

  # This is a P-length vector of Eigenvalues.
  eigenValues = eigens.slice(1, 0, 1)
  # This is a PxP matrix with eigenvectors in rows.
  eigenVectors = eigens.slice(1, 1)

  # Convert the array image to 2D arrays for matrix computations.
  arrayImage = arrays.toArray(1)

  # Left multiply the image array by the matrix of eigenvectors.
  principalComponents = ee.Image(eigenVectors).matrixMultiply(arrayImage)

  # Turn the square roots of the Eigenvalues into a P-band image.
  sdImage = ee.Image(eigenValues.sqrt()) \
    .arrayProject([0]).arrayFlatten([getNewBandNames('sd')])

  # Turn the PCs into a P-band image, normalized by SD.
  return principalComponents \
    .arrayProject([0]) \
    .arrayFlatten([getNewBandNames('pc')]) \
    .divide(sdImage) \


# Get the PCs at the specified scale and in the specified region
pcImage = getPrincipalComponents(centered, scale, region)

Map.addLayer(pcImage.select(0), {}, 'Image')

for i in range(0, bandNames.length().getInfo()):
    band = pcImage.bandNames().get(i).getInfo()
    Map.addLayer(pcImage.select([band]), {'min': -2, 'max': 2}, band)




# %%
"""
## Display Earth Engine data layers 
"""

# %%
Map.addLayerControl() # This line is not needed for ipyleaflet-based Map.
Map