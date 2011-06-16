#!/usr/bin/env python
import re

import wx

import serial

from amc2500 import *


class ConnectDialog(wx.Dialog):
    def __init__(self, parent, id, title):
        wx.Dialog.__init__(self,parent,id,title,size=(250,100))
        self.parent = parent
        sizer = wx.GridSizer(3,2,5,5)
        
        self.port = wx.ComboBox( self, -1, choices = self.scan(),)
        self.debug = wx.CheckBox(self,-1,'Debug');
        self.trace = wx.CheckBox(self,-1,'Trace');
        connect = wx.Button(self,-1,'Connect')
        close = wx.Button(self,-1,'Close')
        connect.Bind(wx.EVT_BUTTON,self.OnConnect,connect)
        close.Bind(wx.EVT_BUTTON,self.OnClose,close)
       
        sizer.AddMany([
            (wx.StaticText(self,-1,"Port:"),0,wx.EXPAND),
            (self.port,0,wx.EXPAND),
            (self.debug,0,wx.EXPAND),
            (self.trace,0,wx.EXPAND),
            (close,0,wx.EXPAND),
            (connect,0,wx.EXPAND)
        ])

        self.SetSizer(sizer)

    def OnConnect(self, event):
        try:
            self.parent.controller = AMC2500(
                port = self.port.GetValue(),
                debug = self.debug.GetValue(),
                trace = self.trace.GetValue())
            self.Close();
        except:
            wx.MessageBox('Connection Failed', 'Error')

    def OnClose(self, event):
        self.Close()

    def scan(self):
        available = []
        for i in range(256):
            try:
                s = serial.Serial(i)
                available.append( s.portstr )
                s.close()   # explicit close 'cause of delayed GC in java
            except serial.SerialException:
                pass
        return available


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

    self.buttons = []

    self.buttons.append(wx.ToggleButton(self,-1,"Spindle"))
    self.Bind(wx.EVT_TOGGLEBUTTON,self.parent.OnSpindle,self.buttons[-1])
    self.sizer.Add(self.buttons[-1],1,wx.EXPAND)

    self.sizer.Add(wx.StaticText(self,-1,"Spindle Speed"),0,wx.EXPAND)
    spindlespeed = wx.Slider(self,-1)
    spindlespeed.SetMax(99)
    self.Bind(wx.EVT_SCROLL_CHANGED,self.parent.OnSpindleSpeed,spindlespeed)
    self.sizer.Add(spindlespeed,0,wx.EXPAND)

    self.buttons.append(wx.ToggleButton(self,-1,"Head"))
    self.Bind(wx.EVT_TOGGLEBUTTON,self.parent.OnHead,self.buttons[-1])
    self.sizer.Add(self.buttons[-1],1,wx.EXPAND)

    self.SetSizer(self.sizer)
    self.SetAutoLayout(1)
    self.sizer.Fit(self)

class PreviewPanel(wx.Panel):
        def __init__(self, parent):
            wx.Panel.__init__( self,parent, size=(390,460))
            self.parent = parent
            sizer = wx.BoxSizer( wx.VERTICAL )
            self.canvas = wx.Panel(self, size=(390,460))
            sizer.Add( self.canvas )
            self.canvas.Bind(wx.EVT_PAINT, self.OnPaint)
            self.canvas.Bind(wx.EVT_LEFT_DOWN, self.OnClick)
            self.SetSizer(sizer)
            self.SetAutoLayout(1)
            self.Show(1)
                       
        def OnPaint(self, event):
            dc = wx.PaintDC(event.GetEventObject())
            self.Clear(dc)
            
        def Clear(self, dc):
            dc.Clear()
            dc.SetPen(wx.Pen("DARKGREY", 1))
            dc.DrawRectangle(0,0,390,431)
            dc.DrawRectangle(55,160,322,271)
            dc.DrawCircle(224,425,2)
            
        def OnClick(self,event):
          pos = (460-event.GetPosition()[1],event.GetPosition()[0]-55)
          coords = map(lambda a: int(a*STEPS_PER_MM), pos)
          if self.parent.controller:
              self.parent.controller.move_to(coords[1],coords[0])
          self.parent.UpdateStatus()
          event.Skip()


class MainFrame(wx.Frame):
  def __init__(self,parent,title):

    self.controller = False

    wx.Frame.__init__(self,parent,title=title,size=(800,600))
    
    self.statusBar = self.CreateStatusBar()

    filemenu = wx.Menu()
  
    connectItem = filemenu.Append(-1, "&Connect", "Connect to a machine")
    aboutItem = filemenu.Append(wx.ID_ABOUT, "&About", " Hacky McHacks to test AMC2500")
    filemenu.AppendSeparator()
    exitItem = filemenu.Append(wx.ID_EXIT, "E&xit", " SIGTERM")

    self.Bind(wx.EVT_MENU,self.OnConnect,connectItem)
    self.Bind(wx.EVT_MENU,self.OnAbout,aboutItem)
    self.Bind(wx.EVT_MENU,self.OnExit,exitItem)

    menubar = wx.MenuBar()
    menubar.Append(filemenu,"&File")
    self.SetMenuBar(menubar)

    self.buttons = []

    self.gotoXYPanel = GotoXYPanel(self)

    self.controls_sizer = wx.BoxSizer(wx.VERTICAL)
    self.controls_sizer.Add(ToolControlPanel(self),2,wx.EXPAND)
    self.controls_sizer.Add(JogPanel(self),3,wx.EXPAND)
    self.controls_sizer.Add(self.gotoXYPanel,1,wx.EXPAND)
    self.controls_sizer.Add(FindCornersPanel(self),3,wx.EXPAND)

    self.buttons.append(wx.Button(self,-1,"Zero Here"))
    self.Bind(wx.EVT_BUTTON,self.OnZeroHere,self.buttons[-1])
    self.controls_sizer.Add(self.buttons[-1],1,wx.EXPAND)

    self.sizer=wx.BoxSizer(wx.HORIZONTAL)
    self.sizer.Add(self.controls_sizer,1,wx.EXPAND)
    self.sizer.Add(PreviewPanel(self),2)
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
        self.controller.jog( 0, 1)
      elif direction == 'W':
        self.controller.jog(-1, 0)
      elif direction == 'E':
        self.controller.jog( 1, 0)
      elif direction == 'S':
        self.controller.jog( 0,-1)
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

  def OnConnect(self,e):
    dlg = ConnectDialog( None, -1, "Connect an AMC2500 Controller" )
    dlg.ShowModal() # Show it
    dlg.Destroy() # finally destroy it when finished.

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

  def OnHead(self,e):
    if(self.controller):
      self.controller.set_head_down(e.GetEventObject().GetValue())
      self.UpdateStatus()
    else:
      e.Skip()

  def OnSpindle(self,e):
    if(self.controller):
      self.controller.set_spindle(e.GetEventObject().GetValue())
      self.UpdateStatus()
    else:
      e.Skip()

  def OnSpindleSpeed(self,e):
    print e.GetEventObject().GetValue()
    if(self.controller):
      self.controller.set_spindle_speed(e.GetEventObject().GetValue())
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

def main():
    app = wx.App(False)
    frame = MainFrame(None,"AMC2500 Jogger")
    app.MainLoop()
    app.Destroy()

if __name__ == "__main__":
    main()

