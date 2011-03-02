#!/usr/bin/env python
import re

import wx

from amc2500 import *

class GotoXYPanel(wx.Panel):
  def __init__(self,parent):
    wx.Panel.__init__(self,parent)
    self.parent = parent
    self.sizer = wx.BoxSizer(wx.HORIZONTAL)

    self.coords = wx.TextCtrl(self, -1, '', style = wx.TE_PROCESS_ENTER)
    self.sizer.Add(self.coords, 2, wx.EXPAND)
    self.coords.Bind(wx.EVT_TEXT_ENTER,self.parent.GotoXY,self.coords)

    self.goButton = wx.Button(self,-1,'Go')
    self.goButton.Bind(wx.EVT_BUTTON,self.parent.GotoXY,self.goButton)
    self.sizer.Add(self.goButton, 0, wx.EXPAND)

    self.SetSizer(self.sizer)
    self.SetAutoLayout(1)
    self.sizer.Fit(self)

class FindCornersPanel(wx.Panel):
  def __init__(self,parent):
    wx.Panel.__init__(self,parent)
    self.parent = parent
    self.sizer = wx.BoxSizer(wx.VERTICAL)
    self.sizer.Add(wx.StaticText(self,1,"Find Corner"),0,wx.EXPAND)
    
    self.sizer2 = wx.GridSizer(2,2)
    self.sizer.Add(self.sizer2,1,wx.EXPAND)
    self.buttons = []

    self.buttons.append(wx.Button(self,-1,'NW'))
    self.sizer2.Add(self.buttons[-1],1,wx.EXPAND)
    self.buttons[-1].Bind(wx.EVT_BUTTON,self.parent.FindCorner,self.buttons[-1])

    self.buttons.append(wx.Button(self,-1,'NE'))
    self.sizer2.Add(self.buttons[-1],1,wx.EXPAND)
    self.buttons[-1].Bind(wx.EVT_BUTTON,self.parent.FindCorner,self.buttons[-1])

    self.buttons.append(wx.Button(self,-1,'SW'))
    self.sizer2.Add(self.buttons[-1],1,wx.EXPAND)
    self.buttons[-1].Bind(wx.EVT_BUTTON,self.parent.FindCorner,self.buttons[-1])

    self.buttons.append(wx.Button(self,-1,'SE'))
    self.sizer2.Add(self.buttons[-1],1,wx.EXPAND)
    self.buttons[-1].Bind(wx.EVT_BUTTON,self.parent.FindCorner,self.buttons[-1])

    self.SetSizer(self.sizer)
    self.SetAutoLayout(1)
    self.sizer.Fit(self)


class JogPanel(wx.Panel):
  def __init__(self,parent):
    wx.Panel.__init__(self,parent)
    self.parent = parent
    self.sizer = wx.GridSizer(2,3)
    self.joggers = []

    self.sizer.Add(wx.StaticText(self,-1,''),1,wx.EXPAND)

    self.joggers.append(wx.Button(self,-1,'N'))
    self.sizer.Add(self.joggers[-1],1,wx.EXPAND)
    self.joggers[-1].Bind(wx.EVT_LEFT_DOWN,self.parent.Jog,self.joggers[-1])
    self.joggers[-1].Bind(wx.EVT_LEFT_UP,self.parent.StopJog,self.joggers[-1])

    self.sizer.Add(wx.StaticText(self,-1,''),1,wx.EXPAND)

    self.joggers.append(wx.Button(self,-1,'W'))
    self.sizer.Add(self.joggers[-1],1,wx.EXPAND)
    self.joggers[-1].Bind(wx.EVT_LEFT_DOWN,self.parent.Jog,self.joggers[-1])
    self.joggers[-1].Bind(wx.EVT_LEFT_UP,self.parent.StopJog,self.joggers[-1])

    self.joggers.append(wx.Button(self,-1,'S'))
    self.sizer.Add(self.joggers[-1],1,wx.EXPAND)
    self.joggers[-1].Bind(wx.EVT_LEFT_DOWN,self.parent.Jog,self.joggers[-1])
    self.joggers[-1].Bind(wx.EVT_LEFT_UP,self.parent.StopJog,self.joggers[-1])

    self.joggers.append(wx.Button(self,-1,'E'))
    self.sizer.Add(self.joggers[-1],1,wx.EXPAND)
    self.joggers[-1].Bind(wx.EVT_LEFT_DOWN,self.parent.Jog,self.joggers[-1])
    self.joggers[-1].Bind(wx.EVT_LEFT_UP,self.parent.StopJog,self.joggers[-1])

    self.SetSizer(self.sizer)
    self.SetAutoLayout(1)
    self.sizer.Fit(self)

class ToolControlPanel(wx.Panel):
  def __init__(self,parent):
    wx.Panel.__init__(self,parent)
    self.parent = parent
  
    self.sizer = wx.BoxSizer(wx.VERTICAL)
    self.sizer1 = wx.BoxSizer(wx.HORIZONTAL)
    self.sizer2 = wx.BoxSizer(wx.HORIZONTAL)

    self.buttons = []

    self.buttons.append(wx.Button(self,-1,"HeadUp"))
    self.Bind(wx.EVT_BUTTON,self.parent.OnHeadUp,self.buttons[-1])
    self.sizer1.Add(self.buttons[-1],1,wx.EXPAND)

    self.buttons.append(wx.Button(self,-1,"HeadDown"))
    self.Bind(wx.EVT_BUTTON,self.parent.OnHeadDown,self.buttons[-1])
    self.sizer1.Add(self.buttons[-1],1,wx.EXPAND)

    self.buttons.append(wx.Button(self,-1,"SpindleOn"))
    self.Bind(wx.EVT_BUTTON,self.parent.OnSpindleOn,self.buttons[-1])
    self.sizer2.Add(self.buttons[-1],1,wx.EXPAND)

    self.buttons.append(wx.Button(self,-1,"SpindleOff"))
    self.Bind(wx.EVT_BUTTON,self.parent.OnSpindleOff,self.buttons[-1])
    self.sizer2.Add(self.buttons[-1],1,wx.EXPAND)

    self.sizer.Add(self.sizer1,1,wx.EXPAND)
    self.sizer.Add(self.sizer2,1,wx.EXPAND)
    self.SetSizer(self.sizer)
    self.SetAutoLayout(1)
    self.sizer.Fit(self)

class MainFrame(wx.Frame):
  def __init__(self,parent,title):

    self.controller = AMC2500() # HACK! TODO: Connection dialog
    #self.controller = False

    wx.Frame.__init__(self,parent,title=title,size=(800,600))
    
    self.statusBar = self.CreateStatusBar()

    filemenu = wx.Menu()
  
    aboutItem = filemenu.Append(wx.ID_ABOUT, "&About", " Hacky McHacks to test AMC2500")
    filemenu.AppendSeparator()
    exitItem = filemenu.Append(wx.ID_EXIT, "E&xit", " SIGTERM")

    self.Bind(wx.EVT_MENU,self.OnAbout,aboutItem)
    self.Bind(wx.EVT_MENU,self.OnExit,exitItem)

    menubar = wx.MenuBar()
    menubar.Append(filemenu,"&File")
    self.SetMenuBar(menubar)

    self.sizer1 = wx.BoxSizer(wx.HORIZONTAL)
    self.sizer3 = wx.BoxSizer(wx.HORIZONTAL)
    self.buttons = []


    self.buttons.append(wx.Button(self,-1,"Zero Here"))
    self.Bind(wx.EVT_BUTTON,self.OnZeroHere,self.buttons[-1])
    self.sizer3.Add(self.buttons[-1],1,wx.EXPAND)

    self.gotoXYPanel = GotoXYPanel(self)

    self.sizer = wx.BoxSizer(wx.VERTICAL)
    self.sizer.Add(ToolControlPanel(self),2,wx.EXPAND)
    self.sizer.Add(JogPanel(self),3,wx.EXPAND)
    self.sizer.Add(self.gotoXYPanel,1,wx.EXPAND)
    self.sizer.Add(FindCornersPanel(self),3,wx.EXPAND)
    self.sizer.Add(self.sizer3,1,wx.EXPAND)

    self.SetSizer(self.sizer)
    self.SetAutoLayout(1)
    self.sizer.Fit(self)


    self.Show(True)
    
  def GotoXY(self,e):
    coords = self.gotoXYPanel.coords.GetValue()
    m = re.search('\(?([\d\.]+),([\d\.]+)\)?', coords)
    if m and self.controller:
      self.controller.move_to(float(m.group(1)), float(m.group(2)))
      self.UpdateStatus()

  def Jog(self,e):
    direction = e.GetEventObject().GetLabel()
    if(self.controller):
      if direction == 'N':
        self.controller.jog( 1, 0)
      elif direction == 'W':
        self.controller.jog( 0,-1)
      elif direction == 'E':
        self.controller.jog( 0, 1)
      elif direction == 'S':
        self.controller.jog(-1, 0)
      self.statusBar.SetStatusText("Jogging %s" % direction)
    e.Skip()

  def FindCorner(self,e):
    direction = e.GetEventObject().GetLabel()
    if(self.controller):
      self.statusBar.SetStatusText("Searching For %s Corner" % direction)
      if direction == 'NW':
        self.controller.find_corner( 1,-1)
      elif direction == 'NE':
        self.controller.find_corner( 1, 1)
      elif direction == 'SW':
        self.controller.find_corner(-1,-1)
      elif direction == 'SE':
        self.controller.find_corner(-1, 1)
      self.UpdateStatus()

  def StopJog(self,e):
    if(self.controller):
      self.controller.stop_jog()
      self.UpdateStatus()
    e.Skip()

  def OnAbout(self,e):
    dlg = wx.MessageDialog( 
      self, 
      "Testing tool for our AMC2500 CNC controller", 
      "AMC2500 Jogger", 
      wx.OK
    )
    dlg.ShowModal() # Show it
    dlg.Destroy() # finally destroy it when finished.

  def OnExit(self,e):
    self.Close(True)  # Close the frame.

  def OnZero(self,e):
    if(self.controller):
      self.controller.zero()
      self.UpdateStatus()
    else:
      e.Skip()

  def OnZeroHere(self,e):
    if(self.controller):
      self.controller.zero_here()
      self.UpdateStatus()
    else:
      e.Skip()

  def OnHeadUp(self,e):
    if(self.controller):
      self.controller.head_down(False)
      self.UpdateStatus()
    else:
      e.Skip()

  def OnHeadDown(self,e):
    if(self.controller):
      self.controller.head_down(True)
      self.UpdateStatus()
    else:
      e.Skip()

  def OnSpindleOn(self,e):
    if(self.controller):
      self.controller.spindle(True)
      self.UpdateStatus()
    else:
      e.Skip()

  def OnSpindleOff(self,e):
    if(self.controller):
      self.controller.spindle(False)
      self.UpdateStatus()
    else:
      e.Skip()

  def OnSomePlaceFun(self,e):
    if(self.controller):
      self.controller.move_to(12000,1000)
      self.UpdateStatus()
    else:
      e.Skip()

  def UpdateStatus(self):
    if(self.controller):
      self.statusBar.SetStatusText(
          "Position: (%d,%d), LimitSwitches(%d,%d)" % (
            self.controller.pos[0],self.controller.pos[1],
            self.controller.limits[0],self.controller.limits[1]
          )
      )

app = wx.App(False)
frame = MainFrame(None,"AMC2500 Jogger")
app.MainLoop()

