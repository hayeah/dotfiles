// Heuristic wrap for `browser eval` input.
//
// Single expression → `return (<code>)` (so `document.title` etc. still works).
// Multi-statement   → code runs as-is inside the async function body; the
//                     caller is responsible for their own `return`.
//
// Detection is practical, not bulletproof: comments and string/template
// literal contents are blanked out (length-preserving) before we scan for
// top-level semicolons and statement keywords.

const STATEMENT_KEYWORD_RE =
	/^(return|throw|break|continue|debugger|if|for|while|do|switch|try|const|let|var|function|class|import|export|async\s+function)\b/;

// Replace string/template literal contents and comments with spaces so that
// character indices in the result line up with the original `code`.
function blankStringsAndComments(code: string): string {
	const out: string[] = [];
	let i = 0;
	const n = code.length;

	const pushSpace = () => out.push(" ");
	const pushKeepNewlines = (ch: string) => out.push(ch === "\n" ? "\n" : " ");

	while (i < n) {
		const c = code[i]!;
		const next = code[i + 1];

		if (c === "/" && next === "/") {
			while (i < n && code[i] !== "\n") {
				pushSpace();
				i++;
			}
			continue;
		}

		if (c === "/" && next === "*") {
			pushSpace();
			pushSpace();
			i += 2;
			while (i < n && !(code[i] === "*" && code[i + 1] === "/")) {
				pushKeepNewlines(code[i]!);
				i++;
			}
			if (i < n) { pushSpace(); i++; }
			if (i < n) { pushSpace(); i++; }
			continue;
		}

		if (c === '"' || c === "'" || c === "`") {
			const quote = c;
			out.push(c);
			i++;
			while (i < n) {
				const cc = code[i]!;
				if (cc === "\\" && i + 1 < n) {
					pushSpace();
					pushSpace();
					i += 2;
					continue;
				}
				if (cc === quote) {
					out.push(cc);
					i++;
					break;
				}
				if (quote === "`" && cc === "$" && code[i + 1] === "{") {
					pushSpace();
					pushSpace();
					i += 2;
					let depth = 1;
					while (i < n && depth > 0) {
						const d = code[i]!;
						if (d === "{") depth++;
						else if (d === "}") depth--;
						pushKeepNewlines(d);
						i++;
					}
					continue;
				}
				pushKeepNewlines(cc);
				i++;
			}
			continue;
		}

		out.push(c);
		i++;
	}
	return out.join("");
}

function hasTopLevelSemicolon(blanked: string): boolean {
	const core = blanked.replace(/[\s;]+$/, "");
	let depth = 0;
	for (let i = 0; i < core.length; i++) {
		const c = core[i];
		if (c === "(" || c === "{" || c === "[") depth++;
		else if (c === ")" || c === "}" || c === "]") depth--;
		else if (c === ";" && depth === 0) return true;
	}
	return false;
}

function startsWithStatementKeyword(blanked: string): boolean {
	return STATEMENT_KEYWORD_RE.test(blanked.trimStart());
}

export function isSingleExpression(code: string): boolean {
	const blanked = blankStringsAndComments(code);
	return !hasTopLevelSemicolon(blanked) && !startsWithStatementKeyword(blanked);
}

// Produce the body for `new AsyncFunction(body)` given user-supplied code.
export function wrapEvalCode(code: string): string {
	if (!isSingleExpression(code)) return code;
	// Drop trailing semicolons / whitespace / comments so they don't land
	// inside `return (...)` and cause a syntax error.
	const blanked = blankStringsAndComments(code);
	const trailing = blanked.match(/[\s;]*$/);
	const endIdx = code.length - (trailing ? trailing[0].length : 0);
	return `return (${code.slice(0, endIdx)})`;
}
