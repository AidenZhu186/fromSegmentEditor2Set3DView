# fromSegmentEditor2Set3DView

Goal: Right inside segment-editor, after clicking "Show 3D", a scripted setup on 3D-view, such as re-focalpoint and other properties in the 3D-view. 

The current issue: 
Right now after "show 3D" being clicked, there is nothing happening inside the 3D-view, since the zoom factor not right and the center point not right. 
I know such scripts work in afterwards-actions after clicking "show 3D", especially I may do it when I open a new module such as "Screen capture":
layoutManager = slicer.app.layoutManager()
threeDWidget = layoutManager.threeDWidget(0)
threeDView = threeDWidget.threeDView()
threeDView.resetFocalPoint()

