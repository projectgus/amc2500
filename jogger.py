#!/usr/bin/env python
import wx
from amc2500 import *

class MainFrame(wx.Frame):
  def __init__(self,parent,title):

    self.controller = AMC2500() # HACK! TODO: Connection dialog

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
    self.buttons = [];

    self.buttons.append(wx.Button(self,-1,"Zero"))
    self.Bind(wx.EVT_BUTTON,self.OnZero,self.buttons[-1])
    self.sizer1.Add(self.buttons[-1],1,wx.EXPAND)

    self.buttons.append(wx.Button(self,-1,"HeadUp"))
    self.Bind(wx.EVT_BUTTON,self.OnHeadUp,self.buttons[-1])
    self.sizer1.Add(self.buttons[-1],1,wx.EXPAND)

    self.buttons.append(wx.Button(self,-1,"HeadDown"))
    self.Bind(wx.EVT_BUTTON,self.OnHeadDown,self.buttons[-1])
    self.sizer1.Add(self.buttons[-1],1,wx.EXPAND)

    self.buttons.append(wx.Button(self,-1,"Take Me Some Place Fun"))
    self.Bind(wx.EVT_BUTTON,self.OnSomePlaceFun,self.buttons[-1])
    self.sizer1.Add(self.buttons[-1],1,wx.EXPAND)

    self.sizer2 = wx.GridSizer(3,3)
    self.joggers = []

    self.joggers.append(wx.StaticText(self,-1,''))
    self.sizer2.Add(self.joggers[-1],1,wx.EXPAND)

    self.joggers.append(wx.Button(self,-1,'N'))
    self.sizer2.Add(self.joggers[-1],1,wx.EXPAND)
    self.joggers[-1].Bind(wx.EVT_LEFT_DOWN,self.StartJog,self.joggers[-1])
    self.joggers[-1].Bind(wx.EVT_LEFT_UP,self.StopJog,self.joggers[-1])

    self.joggers.append(wx.StaticText(self,-1,''))
    self.sizer2.Add(self.joggers[-1],1,wx.EXPAND)

    self.joggers.append(wx.Button(self,-1,'W'))
    self.sizer2.Add(self.joggers[-1],1,wx.EXPAND)
    self.joggers[-1].Bind(wx.EVT_LEFT_DOWN,self.StartJog,self.joggers[-1])
    self.joggers[-1].Bind(wx.EVT_LEFT_UP,self.StopJog,self.joggers[-1])

    self.joggers.append(wx.Button(self,-1,'Zero Here'))
    self.sizer2.Add(self.joggers[-1],1,wx.EXPAND)
    self.Bind(wx.EVT_BUTTON,self.OnZeroHere,self.joggers[-1])

    self.joggers.append(wx.Button(self,-1,'E'))
    self.sizer2.Add(self.joggers[-1],1,wx.EXPAND)
    self.joggers[-1].Bind(wx.EVT_LEFT_DOWN,self.StartJog,self.joggers[-1])
    self.joggers[-1].Bind(wx.EVT_LEFT_UP,self.StopJog,self.joggers[-1])

    self.joggers.append(wx.StaticText(self,-1,''))
    self.sizer2.Add(self.joggers[-1],1,wx.EXPAND)

    self.joggers.append(wx.Button(self,-1,'S'))
    self.sizer2.Add(self.joggers[-1],1,wx.EXPAND)
    self.joggers[-1].Bind(wx.EVT_LEFT_DOWN,self.StartJog,self.joggers[-1])
    self.joggers[-1].Bind(wx.EVT_LEFT_UP,self.StopJog,self.joggers[-1])

    self.joggers.append(wx.StaticText(self,-1,''))
    self.sizer2.Add(self.joggers[-1],1,wx.EXPAND)

    self.sizer = wx.BoxSizer(wx.VERTICAL)
    self.sizer.Add(self.sizer1,1,wx.EXPAND)
    self.sizer.Add(self.sizer2,1,wx.EXPAND)

    self.SetSizer(self.sizer)
    self.SetAutoLayout(1)
    self.sizer.Fit(self)

    self.Show(True)
    
  def StartJog(self,e):
    direction = e.GetEventObject().GetLabel()
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

  def StopJog(self,e):
    self.controller.stop_jog();
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

