import os
#import sys
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin

# 
def get_class_members(klass):
    ret = dir(klass)
    if hasattr(klass,'__bases__'):
        for base in klass.__bases__:
            ret = ret + get_class_members(base)
    return ret

def uniq( seq ): 
    """ the 'set()' way ( use dict when there's no set ) """
    return list(set(seq))

def get_object_attrs( obj ):
    # code borrowed from the rlcompleter module ( see the code for Completer::attr_matches() )
    ret = dir( obj )
    ## if "__builtins__" in ret:
    ##    ret.remove("__builtins__")
    if hasattr( obj, '__class__'):
        ret.append('__class__')
        ret.extend( get_class_members(obj.__class__) )
        ret = uniq( ret )
    return ret
#
# SegmentEditorAiden
#
class SegmentEditorAiden(ScriptedLoadableModule):
  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    import string
    self.parent.title = "Segment Editor"

    self.parent.categories = ['Aiden-Testing-Here'] #["", "Segmentation"] 

    self.parent.dependencies = ["Segmentations", "SubjectHierarchy"]

    self.parent.contributors = ["Csaba Pinter (Queen's University), Andras Lasso (Queen's University)"]
    self.parent.helpText = """ This module allows editing segmentation objects by directly drawing and 
      using segmentaiton tools on the contained segments. Representations other than the labelmap one 
      (which is used for editing) are automatically updated real-time,so for example the closed surface 
      can be visualized as edited in the 3D view. """
    self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """ This work is part of SparKit project, funded by 
      Cancer Care Ontario (CCO)'s ACRU program and Ontario Consortium for 
      Adaptive Interventions in Radiation Oncology (OCAIRO).  """

  def setup(self):
    # Register subject hierarchy plugin
    import SubjectHierarchyPlugins
    scriptedPlugin = slicer.qSlicerSubjectHierarchyScriptedPlugin(None)
    scriptedPlugin.setPythonSource(SubjectHierarchyPlugins.SegmentEditorSubjectHierarchyPlugin.filePath)

#
# SegmentEditorAidenWidget
#
class SegmentEditorAidenWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
  def __init__(self, parent):
    ScriptedLoadableModuleWidget.__init__(self, parent)
    VTKObservationMixin.__init__(self)

    # Members
    self.parameterSetNode = None
    self.editor = None

    self.n_current_segments = 0
    self.n_old_segments = 0

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)
    # Add margin to the sides
    self.layout.setContentsMargins(8,0,8,0)
    #
    # Pre-Setup  
    #
    self.previewImageNodesCollapsibleButton = ctk.ctkCollapsibleButton()
    self.previewImageNodesCollapsibleButton.text = "Image Nodes"
    self.layout.addWidget(self.previewImageNodesCollapsibleButton)
    self.previewImageNodesCollapsibleButton.collapsed = False #True
    presetPS = qt.QFormLayout(self.previewImageNodesCollapsibleButton)

    self.grayscaleSelectorFrame = qt.QFrame(self.parent)
    self.grayscaleSelectorFrame.setLayout(qt.QHBoxLayout())  #qt.QHBoxLayout()
    self.parent.layout().addWidget(self.grayscaleSelectorFrame)

    self.grayscaleSelectorLabel = qt.QLabel("Gray Image: ", self.grayscaleSelectorFrame)
    self.grayscaleSelectorLabel.setToolTip( "Select the grayscale volume (background grayscale scalar volume node) for statistics calculations")
    
    self.grayscaleSelectorFrame.layout().addWidget(self.grayscaleSelectorLabel)

    self.grayscaleSelector = slicer.qMRMLNodeComboBox() # self.grayscaleSelectorFrame)
    self.grayscaleSelector.nodeTypes = ["vtkMRMLScalarVolumeNode"]
    self.grayscaleSelector.selectNodeUponCreation = False
    self.grayscaleSelector.addEnabled = False
    self.grayscaleSelector.removeEnabled = False
    self.grayscaleSelector.noneEnabled = True
    self.grayscaleSelector.showHidden = False
    self.grayscaleSelector.showChildNodeTypes = False
    self.grayscaleSelector.setMRMLScene( slicer.mrmlScene )
    self.grayscaleSelector.setToolTip('Setting to pick up as slicer.mrmlScene')
    self.grayscaleSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.onGrayscaleSelect)

    self.grayscaleSelectorFrame.layout().addWidget(self.grayscaleSelector)
    
    presetPS.addRow(self.grayscaleSelectorFrame)  
    # hide this part, no use  . .... aiden 2019.08.13
    
    #...........................................................................................................................
    self.labelSelectorFrame = qt.QFrame(self.parent) # original code: no-definition of parent self.labelSelectorFrame = qt.QFrame()
    self.labelSelectorFrame.setLayout( qt.QHBoxLayout() )
    #self.labelSelectorFrame.setToolTip('Where am I? self.labelSelectorFrame')
    self.parent.layout().addWidget( self.labelSelectorFrame )
    
    self.labelSelectorLabel = qt.QLabel()
    self.labelSelectorLabel.setText( "Label Map: " )
    
    self.labelSelectorFrame.layout().addWidget(self.labelSelectorLabel)

    self.labelSelector = slicer.qMRMLNodeComboBox()
    self.labelSelector.nodeTypes = ["vtkMRMLLabelMapVolumeNode"]
    self.labelSelector.selectNodeUponCreation = False
    self.labelSelector.addEnabled = False
    self.labelSelector.noneEnabled = True
    self.labelSelector.removeEnabled = False
    self.labelSelector.showHidden = False
    self.labelSelector.showChildNodeTypes = True
    self.labelSelector.setMRMLScene( slicer.mrmlScene )
    self.labelSelector.setToolTip("Pick the label map to edit")
    self.labelSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.onLabelSelect)
   
    self.labelSelectorFrame.layout().addWidget(self.labelSelector)
       

    # Load label into segmentation
    self.applyLabelMapToSegmentationButton = qt.QPushButton('Labels to Segments')
    self.applyLabelMapToSegmentationButton.setToolTip('Pick up a label-map and convert to segments')
    self.applyLabelMapToSegmentationButton.connect('clicked(bool)', self.onApplyLabels2Segments)
    self.labelSelectorFrame.layout().addWidget(self.applyLabelMapToSegmentationButton)
    #...........................................................................................................................
    presetPS.addRow(self.labelSelectorFrame)     

    #
    #BeFixed CheckBox
    # under development.............The goal is try to get customized settings to fix some segments during segment-editing
    #
    self.setBeFixedCheckBox = ctk.ctkCollapsibleButton()
    self.setBeFixedCheckBox.text = 'Set up Fixed Segments'
    self.setBeFixedCheckBox.collapsed = False
    self.layout.addWidget(self.setBeFixedCheckBox)

    beFixedFormLayout = qt.QFormLayout(self.setBeFixedCheckBox)

    self.setBeFixedCheckBox = [] 
    
    qt_form1 = qt.QFrame(self.parent )
    qt_form1_layout = qt.QHBoxLayout()
    qt_form1.setLayout(qt_form1_layout)

    for i_chbx in range(10):  
      tmp_s = str(i_chbx)
      #print(tmp_s)    
      CheckBox = qt.QCheckBox(tmp_s)      
      CheckBox.checked = False 
      CheckBox.setToolTip('Segment # '+ str(i_chbx))
      #CheckBox.setFixedWidth(25)
      CheckBox.connect('clicked(bool)', self.onCheckBoxBeFixedUpdated)
      self.setBeFixedCheckBox.append(CheckBox)
      qt_form1.layout().addWidget(CheckBox)

    beFixedFormLayout.addRow(qt_form1)
    
    qt_form2 = qt.QFrame()
    qt_form2_layout = qt.QHBoxLayout()
    qt_form2.setLayout(qt_form2_layout)

    for i_chbx in range(10,20,1):  
      tmp_s = str(i_chbx)
      #print(tmp_s)    
      CheckBox = qt.QCheckBox(tmp_s)      
      CheckBox.checked = False 
      CheckBox.setToolTip('Segment # '+ str(i_chbx))
      #CheckBox.setFixedWidth(25)
      CheckBox.connect('clicked(bool)', self.onCheckBoxBeFixedUpdated)
      self.setBeFixedCheckBox.append(CheckBox)
      qt_form2.layout().addWidget(CheckBox)
   
    beFixedFormLayout.addRow(qt_form2)
    
    # set them up to be disabled and hiden
    for i in range(20):
      self.setBeFixedCheckBox[i].enabled = False 
      self.setBeFixedCheckBox[i].hide()
    #
    # Above still under development
    #print('&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&')
    #

    #
    # Segment editor widget
    #
    #
    #import qSlicerSegmentationsModuleWidgetsPythonQt    
    #self.editor = qSlicerSegmentationsModuleWidgetsPythonQt.qMRMLSegmentEditorWidget()
    self.editor = slicer.qMRMLSegmentEditorWidget()
    #slicer.util.delayDisplay('edited: self.editor = qSlicerSegmentationsModuleWidgetsPythonQt.qMRMLSegmentEditorWidget() ')
    #self.editor.switchToSegmentationsButtonVisible =True 
        
    #print(get_class_members(self.editor))    
    #print(get_object_attrs(self.editor))

    self.editor.setMaximumNumberOfUndoStates(15)
    # Set parameter node first so that the automatic selections made when the scene is set are saved
    self.selectParameterNode()
    self.editor.setMRMLScene(slicer.mrmlScene)

    self.layout.addWidget(self.editor) # adding the Widgets here to the layout 

    # Observe editor effect registrations to make sure that any effects that are registered
    # later will show up in the segment editor widget. For example, if Segment Editor is set
    # as startup module, additional effects are registered after the segment editor widget is created.
    
    #Events of onSegmentAddedRemoved???
    #self.addObserver(self.editor, self.editor.InvokeCustomModifiedEvent, self.editorAddOrRemoveSegments)

    #Modified by Aiden
    #import qSlicerSegmentationsEditorEffectsPythonQt
    #TODO: For some reason the instance() function cannot be called as a class function although it's static
    #factory = qSlicerSegmentationsEditorEffectsPythonQt.qSlicerSegmentEditorEffectFactory()
    
    #qSlicerSegmentEditorEffectFactory--> Singleton class managing segment editor effect plugins.
    factory = slicer.qSlicerSegmentEditorEffectFactory()    

    #slicer.util.delayDisplay('factory = qSlicerSegmentationsEditorEffectsPythonQt.qSlicerSegmentEditorEffectFactory()')
    self.effectFactorySingleton = factory.instance()
    self.effectFactorySingleton.connect('effectRegistered(QString)', self.editorEffectRegistered)
    
    # Connect observers to scene events
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndImportEvent, self.onSceneEndImport)
   
    # It seems it will work until a 3D-view exists  
    layoutManager = slicer.app.layoutManager()
    if layoutManager: 
      threeDWidget = layoutManager.threeDWidget(0)
      threeDView = threeDWidget.threeDView()
      threeDView.resetFocalPoint()
    
  def onCheckBoxBeFixedUpdated(self):
    print('inside onCheckBoxBeFixedUpdated')

  def editorAddOrRemoveSegments(self, caller, event):
    print('========================= inside editorAddOrRemoveSegments =======================')
    print(event)

  def onApplyLabels2Segments(self):
    print('inside onApplyLabels2Segments ,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,')
    try: 
      for ii in range (self.n_current_segments):
        self.editor.onRemoveSegment()
    except:
      print('nothing to get removed')
      pass 
      

    try: 
      #data here #slicer.mrmlScene.Clear()

      ln = self.labelNode  # labelNaode input from self.labelSelector
      gn = self.grayscaleNode #  grayscaleNode input from self.grayscaleSelector combox

      #print(ln)   #
      #data = slicer.util.arrayFromVolume(ln)   # Working to get numpy array
      #import numpy       
      #vol = (ln.GetImageData())      
      #print('how to get access to data ......................................')     
      #print(ln.GetImageData().GetDimensions())
  
      #  Create segmentation/find segmentation
      segmentationNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLSegmentationNode")
      #slicer.mrmlScene.GetNodesByName('Segmentation')  #AddNewNodeByClass("vtkMRMLSegmentationNode")
      #segmentationNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
      segmentationNode.CreateDefaultDisplayNodes() # only needed for display
      segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode( ln )

      # Create temporary segment editor to get access to effects
      segmentEditorWidget = self.editor #slicer.qMRMLSegmentEditorWidget()
      segmentEditorWidget.setMRMLScene(slicer.mrmlScene)
      segmentEditorNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
      segmentEditorWidget.setMRMLSegmentEditorNode(segmentEditorNode)
      segmentEditorWidget.setSegmentationNode(segmentationNode)
      
      segmentEditorWidget.setMasterVolumeNode( ln )

      # Create segments by thresholding
      import numpy 
      v_max = numpy.max(slicer.util.arrayFromVolume(ln))
      segmentsFromHounsfieldUnits = []
      for i in range(v_max+1):
        segmentsFromHounsfieldUnits.append(['Temp_'+str(i), i , i])
      print(segmentsFromHounsfieldUnits)

      for segmentName, thresholdMin, thresholdMax in segmentsFromHounsfieldUnits:
        # Create segment
        addedSegmentID = segmentationNode.GetSegmentation().AddEmptySegment(segmentName)
        segmentEditorNode.SetSelectedSegmentID(addedSegmentID)
        # Fill by thresholding
        segmentEditorWidget.setActiveEffectByName("Threshold")
        effect = segmentEditorWidget.activeEffect()
        effect.setParameter("MinimumThreshold",str(thresholdMin))
        effect.setParameter("MaximumThreshold",str(thresholdMax))
        effect.self().onApply()
        self.n_current_segments += 1

      self.checkCurrentSegmentsNumber()

      # Delete temporary segment editor
      #segmentEditorWidget = None
      #slicer.mrmlScene.RemoveNode(segmentEditorNode)

      # Compute segment volumes
      #
      #import SegmentStatistics
      #segStatLogic = SegmentStatistics.SegmentStatisticsLogic()
      #segStatLogic.getParameterNode().SetParameter("Segmentation", segmentationNode.GetID())
      #segStatLogic.getParameterNode().SetParameter("ScalarVolume", ln.GetID())
      #segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.enabled","False")
      #segStatLogic.getParameterNode().SetParameter("ScalarVolumeSegmentStatisticsPlugin.voxel_count.enabled","False")
      #segStatLogic.getParameterNode().SetParameter("ScalarVolumeSegmentStatisticsPlugin.volume_mm3.enabled","False")
      #segStatLogic.computeStatistics()
      #segStatLogic.exportToTable(resultsTableNode)
      #segStatLogic.showTable(resultsTableNode)

      # Export segmentation to a labelmap
      #labelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLabelMapVolumeNode')
      #slicer.modules.segmentations.logic().ExportVisibleSegmentsToLabelmapNode(segmentationNode, labelmapVolumeNode, ln)
      #slicer.util.saveNode(labelmapVolumeNode, "c:/tmp/BodyComposition-label.nrrd")
      
      #depress the display of label-map
      slicer.util.setSliceViewerLayers(background=gn, foreground=None, label=ln, foregroundOpacity=None, labelOpacity=0)   

    except AttributeError:
      print('Something must be wrong here xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')
      raise AttributeError
      pass 

      
  def checkCurrentSegmentsNumber(self):
    print('checkCurrentSegmentsNumber')
    if self.n_current_segments != self.n_old_segments:
      if self.n_current_segments > self.n_old_segments:
        for i in range(self.n_current_segments):
          self.setBeFixedCheckBox[i].enabled=True
          self.setBeFixedCheckBox[i].show()
          self.n_old_segments = self.n_current_segments
      if self.n_current_segments < self.n_old_segments:
        for i in range(self.n_current_segments, self.n_old_segments, 1):
          self.setBeFixedCheckBox[i].enabled = False
          self.setBeFixedCheckBox[i].hide()

  def onGrayscaleSelect(self, node):
    self.grayscaleNode = node
    segmentEditorWidget = self.editor 
    segmentEditorWidget.setMasterVolumeNode( node )

  def onLabelSelect(self, node):
    self.labelNode = node
    #self.applyButton.enabled = bool(self.grayscaleNode) and bool(self.labelNode)

  def editorEffectRegistered(self):
    self.editor.updateEffectList()

  def selectParameterNode(self):
    # Select parameter set node if one is found in the scene, and create one otherwise
    SegmentEditorAidenSingletonTag = "SegmentEditorAiden"
    SegmentEditorAidenNode = slicer.mrmlScene.GetSingletonNode(SegmentEditorAidenSingletonTag, "vtkMRMLSegmentEditorNode")
    if SegmentEditorAidenNode is None:
      SegmentEditorAidenNode = slicer.vtkMRMLSegmentEditorNode()
      SegmentEditorAidenNode.SetSingletonTag(SegmentEditorAidenSingletonTag)
      SegmentEditorAidenNode = slicer.mrmlScene.AddNode(SegmentEditorAidenNode)
    if self.parameterSetNode == SegmentEditorAidenNode:
      # nothing changed
      return
    self.parameterSetNode = SegmentEditorAidenNode
    self.editor.setMRMLSegmentEditorNode(self.parameterSetNode)

  def getCompositeNode(self, layoutName):
    """ use the Red slice composite node to define the active volumes """
    count = slicer.mrmlScene.GetNumberOfNodesByClass('vtkMRMLSliceCompositeNode')
    for n in range(count):
      compNode = slicer.mrmlScene.GetNthNodeByClass(n, 'vtkMRMLSliceCompositeNode')
      if layoutName and compNode.GetLayoutName() != layoutName:
        continue
      return compNode

  def getDefaultMasterVolumeNodeID(self):
    layoutManager = slicer.app.layoutManager()
    # Use first background volume node in any of the displayed layouts
    for layoutName in layoutManager.sliceViewNames():
      compositeNode = self.getCompositeNode(layoutName)
      if compositeNode.GetBackgroundVolumeID():
        return compositeNode.GetBackgroundVolumeID()
    # Use first background volume node in any of the displayed layouts
    for layoutName in layoutManager.sliceViewNames():
      compositeNode = self.getCompositeNode(layoutName)
      if compositeNode.GetForegroundVolumeID():
        return compositeNode.GetForegroundVolumeID()
    # Not found anything
    return None

  def enter(self):
    """Runs whenever the module is reopened
    """
    if self.editor.turnOffLightboxes():
      slicer.util.warningDisplay('Segment Editor is not compatible with slice viewers in light box mode.'
        'Views are being reset.', windowTitle='Segment Editor')

    # Allow switching between effects and selected segment using keyboard shortcuts
    self.editor.installKeyboardShortcuts()

    # Set parameter set node if absent
    self.selectParameterNode()
    self.editor.updateWidgetFromMRML()

    # If no segmentation node exists then create one so that the user does not have to create one manually
    if not self.editor.segmentationNodeID():
      segmentationNode = slicer.mrmlScene.GetFirstNode(None, "vtkMRMLSegmentationNode")
      if not segmentationNode:
        segmentationNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLSegmentationNode')
      self.editor.setSegmentationNode(segmentationNode)
      if not self.editor.masterVolumeNodeID():
        masterVolumeNodeID = self.getDefaultMasterVolumeNodeID()
        self.editor.setMasterVolumeNodeID(masterVolumeNodeID)

  def exit(self):
    self.editor.setActiveEffect(None)
    self.editor.uninstallKeyboardShortcuts()
    self.editor.removeViewObservations()

  def onSceneStartClose(self, caller, event):
    self.parameterSetNode = None
    self.editor.setSegmentationNode(None)
    self.editor.removeViewObservations()

  def onSceneEndClose(self, caller, event):
    if self.parent.isEntered:
      self.selectParameterNode()
      self.editor.updateWidgetFromMRML()

  def onSceneEndImport(self, caller, event):
    if self.parent.isEntered:
      self.selectParameterNode()
      self.editor.updateWidgetFromMRML()

  def cleanup(self):
    self.removeObservers()
    self.effectFactorySingleton.disconnect('effectRegistered(QString)', self.editorEffectRegistered)

class SegmentEditorAidenTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    """Currently no testing functionality.
    """
    self.setUp()
    self.test_SegmentEditorAiden1()

  def test_SegmentEditorAiden1(self):
    """Add test here later.
    """
    self.delayDisplay("Starting the test")
    self.delayDisplay('Hhahahha cheating here, Csaba: you are cheating here, no testing at all ')
    self.delayDisplay('Test passed!')

#
# Class for avoiding python error that is caused by the method SegmentEditorAiden::setup
# http://www.na-mic.org/Bug/view.php?id=3871
#
class SegmentEditorAidenFileWriter(object):
  def __init__(self, parent):
    pass
