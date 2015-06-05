#!/usr/bin/env python

import sys
import os
import sqlite3
import ROOT
import subprocess

ROOT.gStyle.SetOptStat(0)
ROOT.gROOT.SetBatch(True)
ROOT.TH1.AddDirectory(False)
ROOT.gErrorIgnoreLevel = ROOT.kWarning

def plot2D(dbh, status = "ENABLED", ytable = "TT_FE_STATUS_BITS"):
  height = dbh.execute("select count(distinct TT_id) from TT_FE_STATUS_BITS where status = '{0}'".format(status)).fetchone()[0]
  minwidth = dbh.execute("select min(run_num) from runs").fetchone()[0]
  maxwidth = dbh.execute("select max(run_num) from runs").fetchone()[0]
  width = maxwidth - minwidth
  #cname = dbh.execute("select name from plots where ytable = 'runs' and xtable = '{0}' and key = '{1}'".format(ytable, status)).fetchone()[0]
  cname = status
  c = ROOT.TCanvas(cname, cname)
  hist = ROOT.TH2F (cname, cname, width + 1, minwidth, maxwidth + 1, height, 1, height)
  hist.SetXTitle("Runs")
  hist.SetYTitle("TT")
  hist.SetMinimum(0)
  hist.SetMaximum(100)
  cur = dbh.cursor()
  xidx = 1
  for x in sorted([i[0] for i in dbh.execute("select distinct run_num from {0}".format(ytable))]):
    yidx = 1
    for y in [j[0] for j in dbh.execute("select distinct TT_id from {0} where status = '{1}'".format(ytable, status))]:
      try:
        tt = cur.execute("select tt, det, sm from TT_IDS where tt_id = {0}".format(y)).fetchone()
        ttname = "{1}{2:+03d}: TT{0}".format(tt[0], tt[1], tt[2])
        sum = cur.execute("select sum(value) from {0} where run_num = {1} and tt_id = {2}".format(ytable, x, y)).fetchone()[0]
        valarr = cur.execute("select value from {0} where run_num = {1} and tt_id = {2} and status = '{3}'".format(ytable, x, y, status)).fetchall()
        if len(valarr) != 0:
          val = valarr[0][0] * 100 / float(sum)
        else:
          val = 0
        print " run: {0:7d}, tt: {1:15s}, status: {2:15s}, value: {3}".format(x, ttname, status, val)
        hist.SetBinContent(xidx, yidx, val)
      except Exception as e:
        print "Do anything: ", str(e)
      hist.GetYaxis().SetBinLabel(yidx, ttname)
      yidx += 1
    hist.GetXaxis().SetBinLabel(xidx, str(x))
    xidx += 1
  hist.LabelsDeflate()
  hist.LabelsOption("v", "X")
#  c.Draw()
  hist.Draw("colz")
  c.Update()
  c.SaveAs("plot_" + status + ".png")

def filldb(dbh, run, rootfile, table = "TT_FE_STATUS_BITS"):
  print "Processing file ", rootfile
  if not os.path.exists(rootfile):
    ret = subprocess.call(['dqm_dumper.py', run], stdout=sys.stdout, stderr=sys.stderr)
    if ret != 0:
        sys.exit(1)

  f = ROOT.TFile(rootfile)
  print "select * from runs where run_num = {0} and root_file = '{1}'".format(run, rootfile)
  if len(dbh.execute("select * from runs where run_num = {0} and root_file = '{1}'".format(run, rootfile)).fetchall()) != 0:
    print "Finished"
    return dbh
  dbh.execute("insert into runs values ({0}, '{1}', '{2}')".format(run, rootfile, 'https://cmsweb.cern.ch/dqm/online/data/browse/ROOT/{0:05d}xxxx/{1:07d}xx/DQM_V0001_{3}_R{2:09d}.root'.format(int(run/10000), int(run/100), run, 'Ecal') ))
  cur = dbh.cursor()
  for (det, maxfe) in zip(["EB", "EE"], [18, 8]):
    for fe in range(-maxfe, maxfe + 1):
      if fe == 0 :
        continue
      print " {0}{1:+03d} ...".format(det, fe)
      fmt = '/DQMData/Run {0}/Ecal{3}/Run summary/{1}StatusFlagsTask/FEStatus/{1}SFT front-end status bits {1}{2:+03d}'
      festatus = f.Get(fmt.format(run, det, fe, 'Barrel' if det == 'EB' else 'Endcap'))
      for tt in range(1, festatus.GetNbinsX() + 1):
        if len(cur.execute("select tt_id from TT_IDS where tt = {0} and det = '{1}' and sm = {2}".format(tt, det, fe)).fetchall()) == 0:
          cur.execute("insert or fail into TT_IDS (tt, det, sm) values ({0}, '{1}', {2})".format(tt, det, fe))
        for status in range(festatus.GetNbinsY()):
          if festatus.GetBinContent(tt, status + 1) > 0:
            label = festatus.GetYaxis().GetBinLabel(status + 1)
            value = festatus.GetBinContent(tt, status + 1)
            sql = "insert into {table} values ({run}, '{status}', {value}, {tt_id})".format(table = table, run = run, status = label, value = value, tt_id = cur.execute("select tt_id from TT_IDS where det = '{0}' and sm = {1} and tt = {2}".format(det, fe, tt)).fetchone()[0] )
            cur.execute(sql)
  dbh.commit()
  print "Finished"
  return dbh

dbh = sqlite3.connect(sys.argv[1])

for i in open('runs.list','r').readlines():
  i = int(i)
  dbh = filldb(dbh, i, 'downloads/DQM_V0001_Ecal_R000{0}.root'.format(i))
dbh.commit()
      
plot2D(dbh, "LINKERROR")
plot2D(dbh, "TIMEOUT")
plot2D(dbh, "HEADERERROR")
plot2D(dbh, "DISABLED")
