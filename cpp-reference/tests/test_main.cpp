// Golden tests on samples/LegacyApp (a synthetic MFC project, no real company code).
// Build: cmake --build build && ./build/mfcgraph_tests   (Windows: build\Release\mfcgraph_tests.exe)
#include <cstdio>
#include <iostream>
#include <string>

#include "index.h"
#include "lexer.h"
#include "query.h"
#include "util.h"

#ifndef MFCGRAPH_SAMPLES
#define MFCGRAPH_SAMPLES "samples/LegacyApp"
#endif

using namespace mg;

static int g_fail = 0, g_pass = 0;

static void check(bool ok, const std::string& what, const std::string& detail = "") {
  if (ok) {
    ++g_pass;
    return;
  }
  ++g_fail;
  std::cout << "FAIL: " << what << "\n";
  if (!detail.empty()) std::cout << "----- output -----\n" << detail << "------------------\n";
}

static void contains(const std::string& out, const std::string& needle, const std::string& what) {
  check(out.find(needle) != std::string::npos, what + "  (expected: " + needle + ")", out);
}

static void not_contains(const std::string& out, const std::string& needle, const std::string& what) {
  check(out.find(needle) == std::string::npos, what + "  (unexpected: " + needle + ")", out);
}

int main(int argc, char** argv) {
  std::string samples = argc > 1 ? argv[1] : MFCGRAPH_SAMPLES;

  // ---- lexer unit checks ----
  {
    auto t = lex("a = R\"x(raw ) string)x\"; b = 1'000; // c\n#define X 1\nL\"w\"", false);
    bool raw_ok = false, num_ok = false, pp_ok = false;
    for (auto& k : t) {
      if (k.k == TK::String && k.s == "raw ) string") raw_ok = true;
      if (k.k == TK::Number && k.s == "1'000") num_ok = true;
      if (k.k == TK::PP && k.s == "define X 1") pp_ok = true;
    }
    check(raw_ok, "lexer: raw string");
    check(num_ok, "lexer: C++14 digit separator");
    check(pp_ok, "lexer: preprocessor line");
    size_t dropped = 0;
    auto f = filter_conditionals(lex("#if 0\n{ {\n#endif\nint x;\n#ifdef A\nint a;\n#else\nint b;\n#endif\n", false),
                                 &dropped);
    std::string joined;
    for (auto& k : f)
      if (k.k != TK::PP) joined += k.s + " ";
    check(joined == "int x ; int a ; ", "lexer: #if 0 skipped, first branch kept", joined);
    auto rc = lex("CAPTION \"Say \"\"hi\"\"\"", true);
    check(rc.size() == 2 && rc[1].s == "Say \"hi\"", "lexer: rc doubled quotes");
  }

  // ---- index the sample project ----
  IndexOptions opt;
  opt.root = samples;
  opt.codepage = 1258;
  Graph built;
  std::string err;
  check(build_index(opt, built, err), "build_index: " + err);
  std::string tmp = path_to_u8(fs::temp_directory_path() / "mfcgraph_test_index.mfg");
  check(save_graph(built, tmp, err), "save_graph: " + err);
  Graph g;
  check(load_graph(tmp, g, err), "load_graph: " + err);
  check(g.nodes.size() == built.nodes.size() && g.edges.size() == built.edges.size(), "save/load round trip");

  // ---- encodings ----
  std::string diag = q_diagnose(g, false);
  contains(diag, "utf16le=1", "UTF-16 .rc detected");
  contains(diag, "ansi:1258=1", "CP1258 source detected");
  contains(diag, "files with unbalanced braces: 0", "#if 0 with unbalanced braces does not break parsing");
  contains(diag, "NOT FOUND 0.0%", "every message-map handler resolved");

  // ---- trace: menu -> command -> handler -> callees ----
  std::string tr = q_trace(g, "Export", 2);
  contains(tr, "Menu IDR_MAINFRAME: File > Export...", "menu caption found");
  contains(tr, "Accelerator Ctrl+E", "accelerator found");
  contains(tr, "handler [ON_COMMAND]: CMainFrame::OnFileExport", "command handler resolved");
  contains(tr, "-> CLegacyDoc::ExportTo", "pDoc->ExportTo resolved through local variable type");
  contains(tr, "CMainFrame::OnUpdateFileExport", "update-UI handler listed");

  // ---- dialog trace: controls, DDX, handlers; CP1258 / UTF-16 text decoded ----
  std::string dt = q_trace(g, "IDD_EXPORT", 2);
  contains(dt, "class: CExportDlg", "dialog class via enum IDD");
  contains(dt, "IDC_EDIT_PATH  EDITTEXT  <-> DDX_Text m_strPath", "DDX binding");
  contains(dt, "-> OnBnClickedBrowse [ON_BN_CLICKED]", "button handler");
  contains(dt, "Xu\xe1\xba\xa5t d\xe1\xbb\xaf li\xe1\xbb\x87u", "Vietnamese caption from UTF-16 .rc");
  contains(dt, "framework entry points: DoDataExchange, OnInitDialog, OnOK", "framework entry points");

  // ---- callers through message routing ----
  std::string cl = q_callers(g, "CMainFrame::OnRecalcDone", 5);
  contains(cl, "WM_APP_RECALC_DONE [ON_MESSAGE]", "ON_MESSAGE custom message");
  contains(cl, "CLegacyDoc::Recalculate", "PostMessage sender linked (heuristic)");
  std::string cl2 = q_callers(g, "CLegacyDoc::Recalculate", 5);
  contains(cl2, "Menu IDR_MAINFRAME: Tools > Recalculate", "callers reach the menu item");
  contains(cl2, "CLegacyView::OnLButtonDown", "GetDocument()->Recalculate() resolved via return type");
  not_contains(cl2, "OnLButtonDown  LegacyView.cpp:48 [likely]", "GetDocument() resolution is exact");

  // ---- ranges, ambiguity, externals ----
  std::string z = q_trace(g, "ID_VIEW_ZOOM_150", 1);
  contains(z, "CLegacyView::OnViewZoom", "ON_COMMAND_RANGE covers ids inside the range");
  std::string ra = q_callees(g, "RefreshAny", 1);
  contains(ra, "CMainFrame::Refresh  MainFrm.cpp:90 [ambiguous]", "unknown receiver -> ambiguous candidates");
  contains(ra, "CView::Invalidate", "((CLegacyView*)p)->Invalidate() resolved via cast type");
  std::string ok = q_callees(g, "CExportDlg::OnOK", 1);
  contains(ok, "AfxMessageBox", "Afx* treated as global");
  not_contains(ok, "CDialog::AfxMessageBox", "Afx* not attributed to the base class");
  std::string mm = q_msgmap(g, "CLegacyApp");
  contains(mm, "CWinApp::OnFileNew  [implemented by MFC base class]", "&CWinApp::OnFileNew recognised");

  // ---- #ifdef: first branch only ----
  std::string wn = q_node(g, "util::WriteTextFile", false, 0);
  contains(wn, "Util.cpp:35", "#ifdef _UNICODE branch chosen");

  // ---- impact & context ----
  std::string im = q_impact(g, "CLegacyDoc::ExportCsv", 5);
  contains(im, "CMainFrame::OnFileExport", "impact reaches the handler");
  contains(im, "Menu IDR_MAINFRAME: File > Export...", "impact reaches the UI");
  std::string cx = q_context(g, "CExportDlg::OnOK", 40);
  contains(cx, "Ch\xc6\xb0\x61 nh\xe1\xba\xadp", "CP1258 source decoded to UTF-8 in snippets");
  contains(cx, "Overrides CDialog::OnOK", "override of MFC virtual");

  // ---- search ----
  std::string se = q_search(g, "recalc", 20);
  contains(se, "[id] ID_TOOLS_RECALC", "search finds IDs");
  contains(se, "Tools > Recalculate", "search finds menu captions");

  std::remove(tmp.c_str());
  std::cout << g_pass << " passed, " << g_fail << " failed\n";
  return g_fail ? 1 : 0;
}
