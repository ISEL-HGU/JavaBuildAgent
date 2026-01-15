# Prompt templates for LLM-based healing

ANALYZE_ERROR_PROMPT = """
You are an expert Java/Build engineer.
Analyze the following build log failure and identify the root cause.

Scope of Analysis:
1. Source Code Errors (Java/internal logic)
2. Build Config Errors (Gradle/Maven plugins, dependencies)
3. Infrastructure/Environment Errors (Docker, Missing Tools, Network, JDK Version)

Build Log:
{build_log}

Instructions:
- If the error is about Docker, identify it clearly.
- If a tool is missing (e.g., "gradle not found"), report it.
- **Look specifically for Version Conflicts (e.g., "library X requires Y > 2.0") and suggest a consistent version.**
- **Look for Missing Symbols (e.g., "cannot find symbol execution") and note the missing class/method.**
- Return strictly valid JSON.

Output Format (JSON):
{{
    "root_cause": "Detailed description (e.g., 'Dependency X v1.0 conflicts with Y v2.0' or 'Missing method foo() in Bar')",
    "file_path": "Path to the file needing fix",
    "confidence": "High/Medium/Low"
}}
"""

GENERATE_PATCH_PROMPT = """
You are an expert Java/Build engineer.
Based on the following error analysis, generate a Python script to fix the issue.
The script will be executed in the project root.
Use standard libraries (os, re, shutil) where possible.
If editing a file, read it, modify the content, and write it back.

Error Analysis:
{analysis}

Root Cause: {root_cause}
Target File: {file_path}

Constraints:
- Return ONLY the Python code block.
- Do not use markdown backticks.
- The code must be self-contained.

Allowed Strategies:
1. **Dependency Update**: If version conflict, update the version in 'pom.xml' or 'build.gradle'.
2. **Code Implementation**: If 'cannot find symbol' (missing method/class), IMPLEMENT a explicit stub or dummy method to satisfy the compiler.
   - Example: Add `public void missingMethod() {{}}` to the class.
3. **Safe Modification**: Do not delete large chunks unless necessary. Prefer fixing or commenting out.


Python Fix Code:
"""

SMART_HEAL_PROMPT = """
You are an expert Senior Build Engineer (Java/Maven/Gradle).
The build has failed. Your goal is to fix it by ANY means necessary.

Context:
- Project Root: . (You are finding files relative to this)
- Build System: Maven or Gradle

Knowledge Base (Common Issues):
1. **Bintray/JCenter Shutdown**: These repositories are dead (SSL errors, 403 Forbidden). You MUST remove them or replace them with Maven Central (`https://repo.maven.apache.org/maven2`).
2. **Restlet Repository**: If `org.restlet` artifacts are missing, they are NOT in Central. You must add this repository:
   `<repository><id>restlet</id><url>https://maven.restlet.talend.com</url></repository>` (or search for a working mirror).
3. **Missing Artifacts**: If an artifact is missing from a repo, try upgrading the version to one available in Maven Central.

Build Log:
{build_log}

Project Structure:
{file_tree}

Instructions:
1. **Analyze** the build failure to find the root cause (e.g., dependency conflict, missing class, compilation error, test failure).
2. **Decide** the best fix strategy. You have full autonomy:
   - **Update Dependency**: Change versions in pom.xml/build.gradle.
   - **Modify Code**: Fix syntax errors, implement missing methods/stubs, change logic.
   - **Neutralize**: comment out (/* */, <!-- -->) problematic tests, plugins, or legacy code if they are blocking the build and seem non-essential.
   - **Create Files**: Create missing files or directories if needed.
3. **Generate** a Python script to apply your fix.
   - The script must be self-contained (import os, re, shutil, pathlib).
   - It must handle file readings and writings using UTF-8.
   - **PATH CRITICAL**: The script runs in the directory shown as root in Project Structure.
     - If Project Structure shows `pom.xml` at the top, open `pom.xml`.
     - Do **NOT** prepend `buggy/` or `/app/buggy/` unless the tree explicitly shows that folder.
     - Do **NOT** use `__file__` (it is undefined in exec() mode). Use `Path(".")` or `os.getcwd()`.

Constraints:
- Return ONLY the Python code block wrapped in ```python ... ```.
- Do not provide explanations outside the code block.
- **COMPATIBILITY**: Use generic Python 3 syntax compatible with Python 3.6+. Do **NOT** use `|` for failure types (e.g. `str | None`). Use `Optional[str]` or no type hints.

Python Fix Code:
"""

