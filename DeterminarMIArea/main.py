# -*- coding: utf-8 -*-
from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsVectorLayer, QgsGeometry, QgsProject, QgsRectangle, QgsGeometry, QgsMapLayer, QgsWkbTypes, QgsPointXY
from qgis.gui import QgsMapToolEmitPoint, QgsVertexMarker, QgsMapToolIdentifyFeature, QgsMapToolIdentify, QgsMapMouseEvent, QgsRubberBand
from qgis.PyQt import uic, QtWidgets, QtCore
from qgis.PyQt.QtWidgets import QFileDialog, QTreeWidgetItem, QHeaderView
from qgis.PyQt.QtCore import pyqtSignal, Qt
from ..auxiliar.auxMI2 import Auxiliar
from .interface_dialog import InterfaceDialog
import processing, gdal, os, requests, tempfile
from PIL import Image


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'detMIArea_dockwidget_base.ui'))


class Main(QtWidgets.QDockWidget, FORM_CLASS):

    closingDock = pyqtSignal()

    def __init__(self, iface):
        super(Main, self).__init__()
        '''Constructor'''
        self.setupUi(self)
        self.iface = iface
        self.dialog = InterfaceDialog()
        self.isOpen = False

    def initGui(self):
        self.initVariables()
        self.initSignals()
        self.openWindow()
        self.isOpen = True

    def openWindow(self):
        self.iface.addDockWidget(QtCore.Qt.RightDockWidgetArea, self)
        self.isOpen = True

    def closeDock(self, event):
        layers = self.iface.mapCanvas().layers()
        for l in layers:
            if l.type() == QgsMapLayer.VectorLayer:
                l.removeSelection()
        self.closingDock.emit()
        event.accept()
        self.isOpen = False
        self.boxButton.setChecked(False)
        self.geometryButton.setChecked(False)
        self.mapList.clear()

    def initVariables(self):
        self.canvas = self.iface.mapCanvas()
        self.myToolBox = RectangleMapTool(self.canvas)
        self.myToolGeom = GeometryMapTool(self.canvas, self.iface)
        self.currentTool = self.canvas.mapTool()
        self.filePathGpkg = Auxiliar().pathGpkg()
        self.scaleSelected = 0
        self.featuresByScale = {1:'',2:'',3:'',4:''}
        self.webParamDict = {1:[975,1090,6,6], 2:[1600,1600,4,4], 3:[1600,1600,4,4], 4:[1450,1200,5,4]} #[width,height,ncol,nrow]

    def initSignals(self):
        self.closeEvent = self.closeDock
        self.boxButton.clicked.connect(self.getFromBox)
        self.geometryButton.clicked.connect(self.getFromGeometry)
        self.myToolBox.boxCreated.connect(self.doWorkBox)
        self.myToolGeom.geometrySelected.connect(self.doWorkGeom)
        self.downloadButton.clicked.connect(self.selectScale)
        self.dialog.finished.connect(self.downloadMaps)
        self.txtButton.clicked.connect(self.exportTxt)
        self.csvButton.clicked.connect(self.exportCsv) 

    def findDataGeom(self, rect, scale):
        scalesDict = {25:1 , 50:2 , 100:3 , 250:4}
        scaleLayer = self.filePathGpkg + "|layername=" + str(scale)
        generalMap = QgsVectorLayer(scaleLayer, "General Map", "ogr")
        generalMap.selectAll()
        featureList = generalMap.selectedFeatures()
        generalMap.removeSelection()
        found = {}
        filteredFeaturesList = []

        for i in featureList:
            if QgsGeometry.fromRect(rect).intersects(i.geometry()):
                found[i[1]] = i[2]
                filteredFeaturesList.append(i)

        self.featuresByScale[scalesDict[scale]] = filteredFeaturesList
        
        return found

    def getFromBox(self, state):
        if state:
            self.mapList.clear()
            self.geometryButton.setChecked(False)
            self.clearLayersSelections()
            self.canvas.setMapTool(self.myToolBox)
            self.canvas.scene().addItem(self.myToolBox.rubberBand)
        else:
            self.canvas.unsetMapTool(self.myToolBox)
            self.canvas.scene().removeItem(self.myToolBox.rubberBand)
            self.myToolBox.reset()

    def getFromGeometry(self, state):
        if state:
            self.mapList.clear()
            self.boxButton.setChecked(False)
            self.myToolBox.reset()
            self.canvas.setMapTool(self.myToolGeom)
        else:
            self.canvas.unsetMapTool(self.myToolGeom)
            self.clearLayersSelections()

    def clearLayersSelections(self):
        layers = self.iface.mapCanvas().layers()
        for l in layers:
            if l.type() == QgsMapLayer.VectorLayer:
                l.removeSelection()

    def doWorkBox(self, r):
        if r is not None:
            f25 = self.findDataGeom(r, 25)
            f50 = self.findDataGeom(r, 50)
            f100 = self.findDataGeom(r, 100)
            f250 = self.findDataGeom(r, 250)

            self.fillListBox(f25, f50, f100, f250)
    
    def doWorkGeom(self, g):
        r = g.boundingBox()
        self.doWorkBox(r)
		
    def fillListBox(self, f25, f50, f100, f250):
        self.mapList.clear()

        scales = (f25, f50, f100, f250)
        item = []

        item.append(QTreeWidgetItem(['1:25.000','']))
        item.append(QTreeWidgetItem(['1:50.000','']))
        item.append(QTreeWidgetItem(['1:100.000','']))
        item.append(QTreeWidgetItem(['1:250.000','']))
        item.append(QTreeWidgetItem([u'Não existentes','']))

        self.mapList.addTopLevelItems([item[0], item[1], item[2], item[3], item[4]])  
        for s in range(4):
            scale_item = scales[s]
            for c in scale_item.keys():
                if scale_item[c] != '':
                    if scale_item[c][0] != '-':
                        item_temp = QTreeWidgetItem([c, scale_item[c]])                                                                
                        item[s].addChild(item_temp)
                    else:
                        item_temp = QTreeWidgetItem([c,''])
                        item[4].addChild(item_temp)
                else:
                    item_temp = QTreeWidgetItem([c,''])
                    item[4].addChild(item_temp)
            item[s].setExpanded(True)

        item[4].setExpanded(True)

        if item[4].childCount() == 0:
            self.mapList.invisibleRootItem().removeChild(item[4])
        
        self.mapList.header().setSectionResizeMode(QHeaderView.ResizeToContents)

    def selectScale(self):
        self.dialog.exec_()

    def processImages(self, layerWMS, webScaleParamList, outputFolder):
        scaleFeaturesList = self.featuresByScale[self.scaleSelected]
        width, height, ncol, nrow =  webScaleParamList
        
        for feat in scaleFeaturesList:
            bboxStr = feat.geometry().boundingBox().asWktCoordinates().replace(',','').split(' ')
            bbox = []
            for i in bboxStr:
                bbox.append(float(i))
            temp_path = tempfile.TemporaryDirectory()
            complete_image = Image.new('RGB', (width * ncol, height * nrow))
            dx = (bbox[2] - bbox[0]) / ncol
            dy = (bbox[3] - bbox[1]) / nrow

            for column in range(ncol):
                xmin = bbox[0] + dx * column
                xmax = bbox[0] + dx * (column + 1)
                for line in range(nrow):
                    ymin = bbox[3] - dy * (line + 1)
                    ymax = bbox[3] - dy * line
                    imageURL = "http://bdgex.eb.mil.br/mapcache?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap&BBOX={},{},{},{}&SRS=EPSG:4326&WIDTH={}&HEIGHT={}&LAYERS={}&STYLES=,,,&FORMAT=image/png&DPI=96&MAP_RESOLUTION=96&FORMAT_OPTIONS=dpi:96&TRANSPARENT=TRUE".format(xmin, ymin, xmax, ymax, width, height, layerWMS)
                    partialImage = requests.get(imageURL, allow_redirects=True)
                    temp_file = temp_path.name + '/temp_image.png'
                    open(temp_file, "wb").write(partialImage.content)
                    complete_image.paste(Image.open(temp_file), (width * column, height * line))
        
            complete_image.save(temp_path.name + '/complete_image.png')
            outputFile = outputFolder + '/' + feat[2] + ".tif"
            
            p1=gdal.GCP(bbox[0], bbox[1], 0, 0, height * nrow)
            p2=gdal.GCP(bbox[2], bbox[1], 0, width * ncol, height * nrow)
            p3=gdal.GCP(bbox[0], bbox[3], 0, 0, 0)
            p4=gdal.GCP(bbox[2], bbox[3], 0, width * ncol, 0)
            
            opt = gdal.TranslateOptions(format = 'GTiff', GCPs = [p1,p2,p3,p4])
            gdal.Translate(outputFile, temp_path.name + '/complete_image.png', options = opt)
            
            processing.run("gdal:assignprojection", {'INPUT': outputFile,
            'CRS' : "EPSG:4326"})
            
        return

    def downloadMaps(self, scaleSelected, outputFolder, multiScale):
        layersDictWeb = {1:"ctm25" , 2:"ctm50" , 3:"ctm100" , 4:"ctm250"}
        self.scaleSelected = scaleSelected
        if multiScale:
            layerWMS = "ctm250,ctm100,ctm50,ctm25"
        else:
            layerWMS = layersDictWeb[scaleSelected]
        webScaleParamList = self.webParamDict[scaleSelected]
        self.processImages(layerWMS, webScaleParamList, outputFolder)
        return

    def exportTxt(self):
        fileDlg = QFileDialog()
        filePath = fileDlg.getSaveFileName(None, u"Selecionar pasta de saída das imagens", "", u"Arquivo texto (*.txt)")[0]
        if filePath != "" and filePath[-4:].lower() != ".txt":
            filePath += ".txt"
        
        if filePath != "":
            csvFile = open(filePath, 'w')

        if filePath == "":
            return

        csvFile.write(u'*********************************************\n')
        head = u'* Lista de cartas topograficas de interesse *\n'
        csvFile.write(head)
        csvFile.write(u'*********************************************\n\n')
        
        itemCount = self.mapList.invisibleRootItem().childCount()
        scale_list = (u'1:25.000', u'1:50.000', u'1:100.000', u'1:250.000')
		
        for i in range(itemCount):
            currentItem = self.mapList.invisibleRootItem().child(i)

            for s in range(4):
                if currentItem.text(0) == scale_list[s]:
                    csvFile.write(scale_list[s]+':\n')
                    csvFile.write(u'---------\n\n')
                    csvFile.write(u'{0:20} | {1:10}\n'.format(u'Nomenclatura', u'MI/MIR'))
                    csvFile.write(u'------------           ------    \n\n')
                
                    for j in range(currentItem.childCount()):
                        csvFile.write(u'{0:20} | {1:10}\n'.format(currentItem.child(j).text(0), currentItem.child(j).text(1)))
                
                    csvFile.write(u'\n')
                    csvFile.write(u'---------------------------------\n\n\n')

        csvFile.close()
    
    def exportCsv(self):
        fileDlg = QFileDialog()
        filePath = fileDlg.getSaveFileName(None, u"Selecionar arquivo de saída", "", u"Arquivo CSV (*.csv)")[0]
        
        if filePath != "" and filePath[-4:].lower() != ".csv":
            filePath += ".csv"
        
        if filePath != "":
            csvFile = open(filePath, 'w')

        if filePath == "":
            return

        csvFile.write(u'Escala;Nomenclatura;MI\n')
        
        itemCount = self.mapList.invisibleRootItem().childCount()
        for i in range(itemCount):
            currentItem = self.mapList.invisibleRootItem().child(i)
            for j in range(currentItem.childCount()):
                csvFile.write(u'{};{};{}\n'.format(currentItem.text(0),currentItem.child(j).text(0), currentItem.child(j).text(1)))
            
        csvFile.close()    




class GeometryMapTool(QgsMapToolIdentifyFeature):
    
    geometrySelected = pyqtSignal(QgsGeometry)
    
    def __init__(self, canvas, iface):
        self.canvas = canvas
        self.iface = iface
        QgsMapToolIdentifyFeature.__init__(self,self.canvas)
      
    def canvasReleaseEvent(self, event):
        event.snapPoint()
        found_features = self.identify(event.x(), event.y(), QgsMapToolIdentify.TopDownStopAtFirst, self.VectorLayer)
    
        layers = self.iface.mapCanvas().layers()
        for l in layers:
            if l.type() == QgsMapLayer.VectorLayer:
                l.selectByIds([])

        if len(found_features) > 0:
            feature = found_features[0].mFeature
            layer = found_features[0].mLayer
            layer.selectByIds([feature.id()])
            geometry = feature.geometry()
            transformer = QgsCoordinateTransform(layer.crs(), QgsCoordinateReferenceSystem(4326, QgsCoordinateReferenceSystem.EpsgCrsId), QgsProject.instance())
            geometry.transform(transformer)
         
        self.geometrySelected.emit(geometry)




class RectangleMapTool(QgsMapToolEmitPoint):
    
    boxCreated = pyqtSignal(QgsRectangle)
    
    def __init__(self, canvas):
        self.canvas = canvas
        QgsMapToolEmitPoint.__init__(self, self.canvas)
        self.rubberBand = QgsRubberBand(self.canvas, QgsWkbTypes().GeometryType(2))
        self.rubberBand.setColor(Qt.red)
        self.rubberBand.setBrushStyle(Qt.Dense6Pattern)
        self.rubberBand.setWidth(1)
        self.reset()

    def reset(self):
        self.startPoint = self.endPoint = None
        self.isEmittingPoint = False
        self.rubberBand.reset(QgsWkbTypes().GeometryType(2))

    def canvasPressEvent(self, e):
        self.startPoint = self.toMapCoordinates(e.pos())
        self.endPoint = self.startPoint
        self.isEmittingPoint = True
        self.showRect(self.startPoint, self.endPoint)

    def canvasReleaseEvent(self, e):
        self.isEmittingPoint = False
        r = self.rectangle()
        if r is not None:
            self.boxCreated.emit(r)

    def canvasMoveEvent(self, e):
        if not self.isEmittingPoint:
            return

        self.endPoint = self.toMapCoordinates(e.pos())
        self.showRect(self.startPoint, self.endPoint)

    def showRect(self, startPoint, endPoint):
        self.rubberBand.reset(QgsWkbTypes().GeometryType(2))
        if startPoint.x() == endPoint.x() or startPoint.y() == endPoint.y():
            return

        point1 = QgsPointXY(startPoint.x(), startPoint.y())
        point2 = QgsPointXY(startPoint.x(), endPoint.y())
        point3 = QgsPointXY(endPoint.x(), endPoint.y())
        point4 = QgsPointXY(endPoint.x(), startPoint.y())

        self.rubberBand.addPoint(point1, False)
        self.rubberBand.addPoint(point2, False)
        self.rubberBand.addPoint(point3, False)
        self.rubberBand.addPoint(point4, True)    # true to update canvas
        self.rubberBand.show()

    def rectangle(self):
        if self.startPoint is None or self.endPoint is None:
            return None
        elif self.startPoint.x() == self.endPoint.x() or self.startPoint.y() == self.endPoint.y():
            return None
        self.rubberBand.hide()
		
        srsCrs = self.canvas.mapSettings().destinationCrs()
        dstCrs = QgsCoordinateReferenceSystem(4326, QgsCoordinateReferenceSystem.EpsgCrsId)
        coordinateTransformer = QgsCoordinateTransform(srsCrs, dstCrs, QgsProject.instance())
        rect = coordinateTransformer.transform(QgsRectangle(self.startPoint, self.endPoint))

        return rect
