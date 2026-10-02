"use client";

import React, { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import { Code2, RotateCcw, Maximize2, Minimize2 } from "lucide-react";
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
}

const DEFAULT_TEMPLATES: Record<string, string> = {
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
  readOnly = false
}: CodeEditorProps) {
  const { resolvedTheme } = useTheme();
  const [fontSize, setFontSize] = useState<number>(14);
  const [editorTheme, setEditorTheme] = useState<string>(resolvedTheme === "dark" ? "vs-dark" : "vs");
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);

  // Sync editor theme with app theme when app theme changes
  useEffect(() => {
    setEditorTheme(resolvedTheme === "dark" ? "vs-dark" : "vs");
  }, [resolvedTheme]);

  const handleResetTemplate = () => {
    const template = DEFAULT_TEMPLATES[language] || "";
    onChange(template);
  };

  const monacoLanguage =
    language === "c" || language === "cpp"
      ? "cpp"
      : language === "javascript" || language === "js" || language === "node"
      ? "javascript"
      : language;

  return (
    <div
      className={`flex flex-col w-full h-full bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-md overflow-hidden ${
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
            className="bg-[var(--bg-surface)] border border-[var(--border-default)] text-[var(--text-primary)] text-xs font-medium rounded px-2 py-1 focus-visible:outline-none cursor-pointer"
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
            className="bg-[var(--bg-surface)] border border-[var(--border-default)] text-[var(--text-secondary)] text-xs rounded px-2 py-1 focus-visible:outline-none cursor-pointer"
            title="Font Size"
            aria-label="Font Size"
          >
            <option value={12}>12px</option>
            <option value={14}>14px</option>
            <option value={16}>16px</option>
            <option value={18}>18px</option>
          </select>

          {/* Theme Selector */}
          <select
            value={editorTheme}
            onChange={(e) => setEditorTheme(e.target.value)}
            className="bg-[var(--bg-surface)] border border-[var(--border-default)] text-[var(--text-secondary)] text-xs rounded px-2 py-1 focus-visible:outline-none cursor-pointer"
            title="Editor Theme"
            aria-label="Editor Theme"
          >
            <option value="vs-dark">Dark Editor</option>
            <option value="vs">Light Editor</option>
          </select>

          {!readOnly && (
            <button
              type="button"
              onClick={handleResetTemplate}
              className="p-1 text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] rounded transition focus-visible:outline-none"
              title="Reset boilerplate template"
              aria-label="Reset Boilerplate"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          )}

          <button
            type="button"
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="p-1 text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] rounded transition focus-visible:outline-none"
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
            padding: { top: 10, bottom: 10 },
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
          }}
        />
      </div>
    </div>
  );
}
