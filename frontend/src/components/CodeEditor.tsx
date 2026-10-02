"use client";

import React, { useState, useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import { Code2, RotateCcw, Maximize2, Minimize2, AlertCircle } from "lucide-react";
import { Spinner } from "./ui/LoadingState";
import { useTheme } from "@/lib/themeContext";

// Dynamically import Monaco Editor to avoid SSR window errors
const Monaco = dynamic(() => import("@monaco-editor/react"), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-full text-xs text-[var(--text-muted)] gap-2">
      <Spinner size="sm" />
      <span>Loading Code Editor...</span>
    </div>
  ),
});

interface CodeEditorProps {
  code: string;
  onChange: (value: string) => void;
  language: string;
  onLanguageChange: (lang: string) => void;
  height?: string;
  readOnly?: boolean;
  onRun?: () => void;
}

export const DEFAULT_TEMPLATES: Record<string, string> = {
  python: `import sys

def solve():
    # Read all inputs from standard input
    input_data = sys.stdin.read().split()
    if not input_data:
        return
    
    # Write your solution logic here
    print("Output")

if __name__ == '__main__':
    solve()
`,
  cpp: `#include <iostream>
#include <vector>
#include <string>
#include <algorithm>
using namespace std;

void solve() {
    // Read inputs from standard input
    int n;
    if (!(cin >> n)) return;
    
    // Write your solution logic here
    cout << n << endl;
}

int main() {
    ios_base::sync_with_stdio(false);
    cin.tie(NULL);
    solve();
    return 0;
}
`,
  c: `#include <stdio.h>
#include <stdlib.h>

int main() {
    // Read inputs from standard input
    int n;
    if (scanf("%d", &n) == 1) {
        // Write your solution logic here
        printf("%d\\n", n);
    }
    return 0;
}
`,
  java: `import java.util.Scanner;

public class Solution {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        if (sc.hasNext()) {
            // Write your solution logic here
            System.out.println("Output");
        }
    }
}
`,
  javascript: `const fs = require('fs');

function solve() {
    const input = fs.readFileSync(0, 'utf-8').trim().split(/\\s+/);
    if (!input || input.length === 0 || input[0] === '') return;

    // Write your solution logic here
    console.log("Output");
}

solve();
`
};

export function CodeEditor({
  code,
  onChange,
  language,
  onLanguageChange,
  height = "100%",
  readOnly = false,
  onRun
}: CodeEditorProps) {
  const { resolvedTheme } = useTheme();
  const [fontSize, setFontSize] = useState<number>(14);
  const [editorTheme, setEditorTheme] = useState<string>(resolvedTheme === "dark" ? "vs-dark" : "vs");
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [showResetConfirm, setShowResetConfirm] = useState<boolean>(false);
  const editorRef = useRef<any>(null);

  // Sync editor theme with app theme when app theme changes
  useEffect(() => {
    setEditorTheme(resolvedTheme === "dark" ? "vs-dark" : "vs");
  }, [resolvedTheme]);

  const handleResetTemplate = () => {
    if (code && code.trim().length > 0 && !showResetConfirm) {
      setShowResetConfirm(true);
      return;
    }
    const template = DEFAULT_TEMPLATES[language] || "";
    onChange(template);
    setShowResetConfirm(false);
  };

  const monacoLanguage =
    language === "c" || language === "cpp"
      ? "cpp"
      : language === "javascript" || language === "js" || language === "node"
      ? "javascript"
      : language;

  const handleEditorDidMount = (editor: any, monaco: any) => {
    editorRef.current = editor;

    // Add Keybinding: Ctrl+Enter / Cmd+Enter to Run Code
    if (onRun) {
      editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => {
        onRun();
      });
    }
  };

  return (
    <div
      className={`flex flex-col w-full h-full bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-lg overflow-hidden ${
        isFullscreen ? "fixed inset-0 z-50 p-4 bg-[var(--bg-canvas)]" : ""
      }`}
    >
      {/* Top Toolbar */}
      <div className="flex items-center justify-between px-3.5 py-2 bg-[var(--bg-subtle)] border-b border-[var(--border-subtle)] shrink-0">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-[var(--text-secondary)]">
            <Code2 className="w-3.5 h-3.5 text-[var(--accent-primary)]" />
            <span className="hidden sm:inline">Language:</span>
          </div>

          <select
            value={language}
            onChange={(e) => onLanguageChange(e.target.value)}
            disabled={readOnly}
            className="bg-[var(--bg-surface)] border border-[var(--border-default)] text-[var(--text-primary)] text-xs font-medium rounded-md px-2.5 py-1 focus-visible:outline-none cursor-pointer"
            aria-label="Select Programming Language"
          >
            <option value="python">Python 3 (CPython)</option>
            <option value="cpp">C++ 17 (g++)</option>
            <option value="c">C (gcc)</option>
            <option value="java">Java 21 (OpenJDK)</option>
            <option value="javascript">JavaScript (Node.js)</option>
          </select>
        </div>

        <div className="flex items-center gap-1.5">
          {/* Font Size Selector */}
          <select
            value={fontSize}
            onChange={(e) => setFontSize(Number(e.target.value))}
            className="bg-[var(--bg-surface)] border border-[var(--border-default)] text-[var(--text-secondary)] text-xs rounded-md px-2 py-1 focus-visible:outline-none cursor-pointer"
            title="Font Size"
            aria-label="Font Size"
          >
            <option value={12}>12px</option>
            <option value={13}>13px</option>
            <option value={14}>14px</option>
            <option value={15}>15px</option>
            <option value={16}>16px</option>
            <option value={18}>18px</option>
          </select>

          {/* Theme Selector */}
          <select
            value={editorTheme}
            onChange={(e) => setEditorTheme(e.target.value)}
            className="bg-[var(--bg-surface)] border border-[var(--border-default)] text-[var(--text-secondary)] text-xs rounded-md px-2 py-1 focus-visible:outline-none cursor-pointer"
            title="Editor Theme"
            aria-label="Editor Theme"
          >
            <option value="vs-dark">Dark Editor</option>
            <option value="vs">Light Editor</option>
          </select>

          {!readOnly && (
            <div className="relative">
              <button
                type="button"
                onClick={handleResetTemplate}
                className="p-1.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] rounded-md transition focus-visible:outline-none"
                title="Reset boilerplate template"
                aria-label="Reset Boilerplate"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>

              {showResetConfirm && (
                <div className="absolute right-0 top-8 z-50 w-56 p-3 rounded-lg bg-[var(--bg-surface)] border border-[var(--border-focus)] shadow-lg space-y-2 text-xs">
                  <div className="flex items-start gap-1.5 text-amber-500 font-semibold">
                    <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                    <span>Reset code template?</span>
                  </div>
                  <p className="text-[11px] text-[var(--text-secondary)]">Your current code will be replaced with standard starter code.</p>
                  <div className="flex items-center justify-end gap-1.5 pt-1">
                    <button
                      type="button"
                      onClick={() => setShowResetConfirm(false)}
                      className="px-2 py-0.5 rounded text-[10px] text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={handleResetTemplate}
                      className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500 text-white"
                    >
                      Reset
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          <button
            type="button"
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="p-1.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] rounded-md transition focus-visible:outline-none"
            title={isFullscreen ? "Exit Fullscreen" : "Fullscreen"}
            aria-label={isFullscreen ? "Exit Fullscreen" : "Enter Fullscreen"}
          >
            {isFullscreen ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* Editor Body */}
      <div className="flex-1 w-full min-h-[260px] overflow-hidden">
        <Monaco
          height="100%"
          language={monacoLanguage}
          theme={editorTheme}
          value={code}
          onChange={(val) => onChange(val || "")}
          onMount={handleEditorDidMount}
          options={{
            fontSize,
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            automaticLayout: true,
            tabSize: 4,
            insertSpaces: true,
            readOnly,
            lineNumbers: "on",
            wordWrap: "on",
            padding: { top: 12, bottom: 12 },
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace",
            bracketPairColorization: { enabled: true },
            cursorBlinking: "smooth",
            cursorSmoothCaretAnimation: "on",
            renderWhitespace: "selection",
            formatOnPaste: true,
            formatOnType: true,
            guides: { indentation: true, bracketPairs: true },
            suggestOnTriggerCharacters: true,
            acceptSuggestionOnEnter: "on"
          }}
        />
      </div>
    </div>
  );
}

