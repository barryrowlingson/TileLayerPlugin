# -*- coding: utf-8 -*-
"""
/***************************************************************************
 TileLayer Plugin
                                 A QGIS plugin
 Plugin layer for Tile Maps
                              -------------------
        begin                : 2012-12-16
        copyright            : (C) 2013 by Minoru Akagi
        email                : akaginch@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
# Import the PyQt and QGIS libraries
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import QgsRectangle

import math

R = 6378137

class TileDefaultSettings:

  ZMIN = 10
  ZMAX = 15

def degreesToMercatorMeters(lon, lat):
  # formula: http://en.wikipedia.org/wiki/Mercator_projection#Mathematics_of_the_Mercator_projection
  x = R * lon * math.pi / 180
  y = R * math.log(math.tan(math.pi / 4 + (lat * math.pi / 180) / 2))
  return x, y

def degreesToTile(zoom, lon, lat):    #TODO: move into TileServiceInfo
  x, y = degreesToMercatorMeters(lon, lat)
  size = TileServiceInfo.TSIZE1 / 2 ** (zoom - 1)
  tx = int((x + TileServiceInfo.TSIZE1) / size)
  ty = int((TileServiceInfo.TSIZE1 - y) / size)
  return tx, ty

class BoundingBox:
  def __init__(self, xmin, ymin, xmax, ymax):
    self.xmin = xmin
    self.ymin = ymin
    self.xmax = xmax
    self.ymax = ymax

  def toQgsRectangle(self):
    return QgsRectangle(self.xmin, self.ymin, self.xmax, self.ymax)

  def toString(self, digitsAfterPoint=None):
    if digitsAfterPoint is None:
      return "%f,%f,%f,%f" % (self.xmin, self.ymin, self.xmax, self.ymax)
    return "%.{0}f,%.{0}f,%.{0}f,%.{0}f".format(digitsAfterPoint) % (self.xmin, self.ymin, self.xmax, self.ymax)

  @classmethod
  def degreesToMercatorMeters(cls, bbox):
    xmin, ymin = degreesToMercatorMeters(bbox.xmin, bbox.ymin)
    xmax, ymax = degreesToMercatorMeters(bbox.xmax, bbox.ymax)
    return BoundingBox(xmin, ymin, xmax, ymax)

  @classmethod
  def degreesToTileRange(cls, zoom, bbox):
    xmin, ymin = degreesToTile(zoom, bbox.xmin, bbox.ymax)
    xmax, ymax = degreesToTile(zoom, bbox.xmax, bbox.ymin)
    return BoundingBox(xmin, ymin, xmax, ymax)

  @classmethod
  def fromString(cls, s):
    a = map(float, s.split(","))
    return BoundingBox(a[0], a[1], a[2], a[3])

class Tile:
  def __init__(self, zoom, x, y, data=None):
    self.zoom = zoom
    self.x = x
    self.y = y
    self.data = data

class Tiles:

  def __init__(self, zoom, xmin, ymin, xmax, ymax, serviceInfo):
    self.zoom = zoom
    self.xmin = xmin
    self.ymin = ymin
    self.xmax = xmax
    self.ymax = ymax
    self.TILE_SIZE = serviceInfo.TILE_SIZE
    self.TSIZE1 = serviceInfo.TSIZE1
    self.yOriginTop = serviceInfo.yOriginTop
    self.serviceInfo = serviceInfo

    self.tiles = {}
    self.cachedImage = None

  def addTile(self, url, tile):
    self.tiles[url] = tile
    self.cachedImage = None

  def setImageData(self, url, data):
    if url in self.tiles:
      self.tiles[url].data = data
    self.cachedImage = None

  def image(self):
    if self.cachedImage:
      return self.cachedImage
    width = (self.xmax - self.xmin + 1) * self.TILE_SIZE
    height = (self.ymax - self.ymin + 1) * self.TILE_SIZE
    image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
    p = QPainter(image)
    for tile in self.tiles.values():
      if tile.data is None:
        continue

      x = tile.x - self.xmin
      y = tile.y - self.ymin
      rect = QRect(x * self.TILE_SIZE, y * self.TILE_SIZE, self.TILE_SIZE, self.TILE_SIZE)

      timg = QImage()
      timg.loadFromData(tile.data)
      p.drawImage(rect, timg)
    self.cachedImage = image
    return image

  def extent(self):
    size = self.TSIZE1 / 2 ** (self.zoom - 1)
    topLeft = QPointF(self.xmin * size - self.TSIZE1, self.TSIZE1 - self.ymin * size)
    bottomRight = QPointF((self.xmax + 1) * size - self.TSIZE1, self.TSIZE1 - (self.ymax + 1) * size)
    return QRectF(topLeft, bottomRight)

class TileServiceInfo:

  TILE_SIZE = 256
  TSIZE1 = 20037508.342789244

  def __init__(self, title, providerName, serviceUrl, yOriginTop=1, zmin=TileDefaultSettings.ZMIN, zmax=TileDefaultSettings.ZMAX, bbox=None):
    self.title = title
    self.providerName = providerName
    self.serviceUrl = serviceUrl
    self.yOriginTop = yOriginTop
    self.zmin = zmin
    self.zmax = zmax
    self.bbox = bbox

  def tileUrl(self, zoom, x, y):
    if not self.yOriginTop:
      y = (2 ** zoom - 1) - y
    return self.serviceUrl.replace("{z}", str(zoom)).replace("{x}", str(x)).replace("{y}", str(y))

  def getMapRect(self, zoom, x, y):
    size = self.TSIZE1 / 2 ** (zoom - 1)
    return QgsRectangle(x * size - self.TSIZE1, self.TSIZE1 - y * size, (x + 1) * size - self.TSIZE1, self.TSIZE1 - (y + 1) * size)

  def __str__(self):
    return "%s (%s)" % (self.title, self.serviceUrl)

  def toArrayForTreeView(self):
    extent = ""
    if self.bbox:
      extent = self.bbox.toString(2)
    return [self.title, self.providerName, self.serviceUrl, "%d-%d" % (self.zmin, self.zmax), extent, self.yOriginTop]

  @classmethod
  def createEmptyInfo(cls):
    return TileServiceInfo("", "", "")