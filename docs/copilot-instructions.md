<!-- Copy this file to .github/copilot-instructions.md in the company repository. -->

This is a legacy C++/MFC codebase. An MCP server "mfcgraph" indexes it.

- Call the `mfc_explore` tool first for any bug, question, or before an edit, before opening files.
- Treat the source it returns as already read. Do not re-open or grep those lines.
- If you need more, call `mfc_explore` again with more specific names: a function from "Not shown", `Class::Method`, or `File.cpp:a-b` from an elision marker.
- Do not rebuild call flows by hand. Name both ends and let the tool find the path.
- Functions flagged msg-handler, update-ui-handler or framework-entry are called by MFC (message map or virtual override), not by other code. Do not treat them as dead code.
- If the result shows "⚠ Changed since last index", ask the user to re-run `index` on the project. The code of the changed files is not shown until then.
- If the MCP tool is unavailable, ask the user to attach the context file made by `mfcgraph explore "<question>" > ctx.md`.
