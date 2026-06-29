let PROBLEM_IDS = ["palindrome"];
let PROBLEM_META = {};
let currentProblemIndex = 0;
let problemId = PROBLEM_IDS[currentProblemIndex];
let activeModel = null;

let starterCode = "";
let editor = null;
let lastSelectedOption = null;

const OPTION_ORDER = [
  "concept_suggestion",
  "code_suggestion",
  "direct_code",
];

let localOptionCounts = {
  concept_suggestion: 0,
  code_suggestion: 0,
  direct_code: 0,
};

function getCurrentProblemId() {
  return PROBLEM_IDS[currentProblemIndex] || "palindrome";
}

async function loadActiveModel() {
  try {
    const response = await fetch("/health", { cache: "no-store" });

    if (!response.ok) {
      return;
    }

    const data = await response.json();
    activeModel = data.model || null;
  } catch (error) {
    console.warn("Could not load active model", error);
  }
}

async function loadProblemIds() {
  try {
    const response = await fetch("/problems", { cache: "no-store" });

    if (!response.ok) {
      throw new Error("Could not load problems list");
    }

    const data = await response.json();
    const problems = data.problems || [];
    const ids = problems
      .map((problem) => problem.id)
      .filter(Boolean);

    PROBLEM_META = {};
    problems.forEach((problem) => {
      if (problem.id) {
        PROBLEM_META[problem.id] = problem;
      }
    });

    if (ids.length > 0) {
      PROBLEM_IDS = ids;
      currentProblemIndex = 0;
      problemId = getCurrentProblemId();
    }
  } catch (error) {
    console.warn("Using fallback problem list", error);
  }
}

function clearBoxes() {
  const helperResponse = document.getElementById("helperResponse");
  const testResults = document.getElementById("testResults");

  if (helperResponse) {
    helperResponse.textContent = "";
  }

  if (testResults) {
    testResults.textContent = "";
  }
}

function setCurrentProblemByIndex(index) {
  if (index < 0 || index >= PROBLEM_IDS.length) {
    return;
  }

  currentProblemIndex = index;
  problemId = getCurrentProblemId();

  lastSelectedOption = null;
  showSelectedOption(null);
  clearBoxes();
  loadProblem();
}

function setCurrentProblemById(selectedProblemId) {
  const index = PROBLEM_IDS.indexOf(selectedProblemId);

  if (index === -1) {
    return;
  }

  setCurrentProblemByIndex(index);
}

function nextProblem() {
  if (currentProblemIndex < PROBLEM_IDS.length - 1) {
    setCurrentProblemByIndex(currentProblemIndex + 1);
  }
}

function previousProblem() {
  if (currentProblemIndex > 0) {
    setCurrentProblemByIndex(currentProblemIndex - 1);
  }
}

function updateProblemControls() {
  const problemSelect =
    document.getElementById("problemSelect") ||
    document.getElementById("problemSelector");

  if (problemSelect) {
    problemSelect.value = getCurrentProblemId();
  }

  const problemCounter = document.getElementById("problemCounter");

  if (problemCounter) {
    problemCounter.textContent =
      `Problem ${currentProblemIndex + 1} of ${PROBLEM_IDS.length}`;
  }

  const previousButton = document.getElementById("previousProblemBtn");
  const nextButton = document.getElementById("nextProblemBtn");

  if (previousButton) {
    previousButton.disabled = currentProblemIndex === 0;
  }

  if (nextButton) {
    nextButton.disabled = currentProblemIndex === PROBLEM_IDS.length - 1;
  }
}

function setupProblemControls() {
  const problemSelect =
    document.getElementById("problemSelect") ||
    document.getElementById("problemSelector");

  if (problemSelect) {
    problemSelect.innerHTML = "";

    PROBLEM_IDS.forEach((id, index) => {
      const option = document.createElement("option");
      option.value = id;
      const meta = PROBLEM_META[id] || {};
      const title = meta.title || id;
      option.textContent = `${index + 1}. ${title} (${id})`;
      problemSelect.appendChild(option);
    });

    problemSelect.addEventListener("change", function () {
      setCurrentProblemById(problemSelect.value);
    });
  }

  const previousButton = document.getElementById("previousProblemBtn");
  const nextButton = document.getElementById("nextProblemBtn");

  if (previousButton) {
    previousButton.addEventListener("click", previousProblem);
  }

  if (nextButton) {
    nextButton.addEventListener("click", nextProblem);
  }

  updateProblemControls();
}

function getCode() {
  return editor ? editor.getValue() : "";
}

function setCode(value) {
  if (editor) {
    editor.setValue(value || "");
  }
}

function getParticipantId() {
  const input = document.getElementById("participantId");
  const value = input ? input.value.trim() : "";
  return value || "pilot";
}

function getMethod() {
  const method = document.getElementById("method");
  return method ? method.value : "normal_selector";
}

function canonicalOption(value) {
  if (!value) {
    return null;
  }

  const key = String(value)
    .trim()
    .toLowerCase()
    .replace(/[_-]/g, " ")
    .replace(/[^a-z0-9\s.]/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  if (
    key === "1" ||
    key.startsWith("1 ") ||
    key.includes("concept") ||
    key.includes("hint") ||
    key.includes("empower") ||
    key.includes("general")
  ) {
    return "concept_suggestion";
  }

  if (
    key === "2" ||
    key.startsWith("2 ") ||
    key.includes("code suggestion") ||
    key.includes("code suggest") ||
    key.includes("snippet") ||
    key === "code"
  ) {
    return "code_suggestion";
  }

  if (
    key === "3" ||
    key.startsWith("3 ") ||
    key.includes("direct code") ||
    key.includes("full code") ||
    key.includes("complete code") ||
    (key.includes("direct") && key.includes("code"))
  ) {
    return "direct_code";
  }

  return null;
}

function labelForSelectedOption(value) {
  const option = canonicalOption(value);

  const labels = {
    concept_suggestion: "Concept suggestion",
    code_suggestion: "Code suggestion",
    direct_code: "Direct code",
  };

  return labels[option] || "Unknown";
}

function showSelectedOption(value) {
  const box = document.getElementById("selectedOptionBox");

  if (!box) {
    return;
  }

  box.textContent = value
    ? labelForSelectedOption(value)
    : "No option chosen yet.";
}

function normalizeCounts(optionCounts) {
  const normalized = {
    concept_suggestion: 0,
    code_suggestion: 0,
    direct_code: 0,
  };

  Object.entries(optionCounts || {}).forEach(([key, value]) => {
    const option = canonicalOption(key);

    if (OPTION_ORDER.includes(option)) {
      normalized[option] += Number(value) || 0;
    }
  });

  return normalized;
}

function calculatePercentages(counts, totalOverride = null) {
  const total = Number.isFinite(Number(totalOverride))
    ? Number(totalOverride)
    : OPTION_ORDER.reduce((sum, option) => {
        return sum + (Number(counts[option]) || 0);
      }, 0);

  if (total === 0) {
    return {
      concept_suggestion: "0.0",
      code_suggestion: "0.0",
      direct_code: "0.0",
    };
  }

  return {
    concept_suggestion: ((counts.concept_suggestion / total) * 100).toFixed(1),
    code_suggestion: ((counts.code_suggestion / total) * 100).toFixed(1),
    direct_code: ((counts.direct_code / total) * 100).toFixed(1),
  };
}

function showCounts(optionCounts, optionTotal = null) {
  const counts = normalizeCounts(optionCounts);

  const total = Number.isFinite(Number(optionTotal))
    ? Number(optionTotal)
    : counts.concept_suggestion + counts.code_suggestion + counts.direct_code;

  const percentages = calculatePercentages(counts, total);

  const metricsBox = document.getElementById("metricsBox");

  if (!metricsBox) {
    return;
  }

  metricsBox.textContent =
    `Stats filters:\n` +
    `Participant: ${getParticipantId()}\n` +
    `Problem: ${getCurrentProblemId()}\n` +
    `Condition: ${getMethod()}\n` +
    `Model: ${activeModel || "all/unknown"}\n\n` +
    `Total helper requests: ${total}\n` +
    `Concept suggestion: ${counts.concept_suggestion} (${percentages.concept_suggestion}%)\n` +
    `Code suggestion: ${counts.code_suggestion} (${percentages.code_suggestion}%)\n` +
    `Direct code: ${counts.direct_code} (${percentages.direct_code}%)`;
}

function showLocalCounts() {
  const total =
    localOptionCounts.concept_suggestion +
    localOptionCounts.code_suggestion +
    localOptionCounts.direct_code;

  showCounts(localOptionCounts, total);
}

function incrementLocalCount(option) {
  const canonical = canonicalOption(option);

  if (!OPTION_ORDER.includes(canonical)) {
    return;
  }

  localOptionCounts[canonical] += 1;
  showLocalCounts();
}

function cleanSuggestionText(text) {
  if (text === null || text === undefined) {
    return "";
  }

  let cleaned = String(text).trim();

  cleaned = cleaned.replace(/^```[a-zA-Z0-9_-]*\s*/g, "");
  cleaned = cleaned.replace(/```$/g, "");
  cleaned = cleaned.trim();

  cleaned = cleaned.replace(/^Model chose .*?(\n\n|\n|$)/i, "").trim();

  if (["none", "null", "undefined"].includes(cleaned.toLowerCase())) {
    return "";
  }

  return cleaned;
}

async function loadProblem() {
  const activeProblemId = getCurrentProblemId();

  try {
    const response = await fetch(`/problems/${activeProblemId}`, {
      cache: "no-store",
    });

    if (!response.ok) {
      throw new Error(`Problem not found: ${activeProblemId}`);
    }

    const problem = await response.json();

    document.getElementById("problemTitle").textContent = problem.title;
    document.getElementById("problemDescription").textContent =
      problem.description;

    starterCode = problem.starter_code || "";
    setCode(starterCode);

    lastSelectedOption = null;
    showSelectedOption(null);

    localOptionCounts = {
      concept_suggestion: 0,
      code_suggestion: 0,
      direct_code: 0,
    };

    updateProblemControls();
    await refreshOptionCounts();
    await refreshStudySummary();
  } catch (error) {
    document.getElementById("problemTitle").textContent = "Problem loading failed";
    document.getElementById("problemDescription").textContent = error.message;
    setCode("");
    showLocalCounts();
  }
}

function resetCode() {
  setCode(starterCode);

  lastSelectedOption = null;
  clearBoxes();
  showSelectedOption(null);
  refreshOptionCounts();
  refreshStudySummary();
}

async function refreshOptionCounts() {
  const participantId = getParticipantId();
  const activeProblemId = getCurrentProblemId();
  const method = getMethod();

  const params = new URLSearchParams({
    participant_id: participantId,
    problem_id: activeProblemId,
    method: method,
  });

  if (activeModel) {
    params.set("model", activeModel);
  }

  try {
    const response = await fetch(`/stats/options?${params.toString()}`, {
      cache: "no-store",
    });

    if (!response.ok) {
      showLocalCounts();
      return;
    }

    const data = await response.json();

    const counts = normalizeCounts(data.option_counts || {});
    const totalFromCounts =
      counts.concept_suggestion +
      counts.code_suggestion +
      counts.direct_code;

    const total = Number.isFinite(Number(data.option_total))
      ? Number(data.option_total)
      : totalFromCounts;

    localOptionCounts = counts;
    showCounts(counts, total);
  } catch (error) {
    console.error("Could not refresh option counts", error);
    showLocalCounts();
  }
}


function formatStudySummary(data) {
  if (!data || !data.overall) {
    return "No summary available yet.";
  }

  const overall = data.overall || {};
  const problems = data.problems || [];
  const counts = overall.option_counts || {};

  const lines = [];

  lines.push("OVERALL SUMMARY");
  lines.push("===============");
  lines.push(`Participant: ${data.participant_id || getParticipantId()}`);
  lines.push(`Condition: ${data.method || getMethod()}`);
  lines.push(`Model: ${data.model || activeModel || "all/unknown"}`);
  lines.push("");
  lines.push(`Problems attempted: ${overall.attempted_problem_count || 0}`);
  lines.push(`Problems passed at least once: ${overall.solved_problem_count || 0}`);
  lines.push(`Problems currently/latest passed: ${overall.latest_passed_problem_count || 0}`);
  lines.push(`Total helper requests: ${overall.helper_requests || 0}`);
  lines.push(`Total test runs: ${overall.test_runs || 0}`);
  lines.push(`Passed test runs: ${overall.passed_test_runs || 0}`);
  lines.push(`Failed test runs: ${overall.failed_test_runs || 0}`);
  lines.push(`Average helper response length: ${overall.suggestion_length_avg || 0} chars`);
  lines.push("");
  lines.push("Helper option choices:");
  lines.push(`- Concept suggestion: ${counts.concept_suggestion || 0}`);
  lines.push(`- Code suggestion: ${counts.code_suggestion || 0}`);
  lines.push(`- Direct code: ${counts.direct_code || 0}`);
  lines.push("");
  lines.push("PROBLEM-WISE SUMMARY");
  lines.push("====================");

  if (problems.length === 0) {
    lines.push("No problem activity logged yet.");
    return lines.join("\n");
  }

  problems.forEach((problem, index) => {
    const problemCounts = problem.option_counts || {};
    const status = problem.passed_once
      ? "PASSED"
      : problem.test_runs > 0
        ? "NOT PASSED"
        : "NO TEST RUN";

    lines.push(`${index + 1}. ${problem.title || problem.problem_id} (${problem.problem_id})`);
    lines.push(`   Status: ${status}`);
    lines.push(`   Helper requests: ${problem.helper_requests || 0}`);
    lines.push(`   Test runs: ${problem.test_runs || 0}`);
    lines.push(`   Passed test runs: ${problem.passed_test_runs || 0}`);
    lines.push(`   Failed test runs: ${problem.failed_test_runs || 0}`);
    lines.push(
      `   Options: concept=${problemCounts.concept_suggestion || 0}, ` +
      `code=${problemCounts.code_suggestion || 0}, ` +
      `direct=${problemCounts.direct_code || 0}`
    );
    lines.push(`   Avg helper length: ${problem.suggestion_length_avg || 0} chars`);
    lines.push("");
  });

  return lines.join("\n");
}

async function refreshStudySummary() {
  const summaryBox = document.getElementById("summaryBox");

  if (!summaryBox) {
    return;
  }

  const params = new URLSearchParams({
    participant_id: getParticipantId(),
    method: getMethod(),
  });

  if (activeModel) {
    params.set("model", activeModel);
  }

  try {
    const response = await fetch(`/stats/summary?${params.toString()}`, {
      cache: "no-store",
    });

    if (!response.ok) {
      let errorText = "";
      try {
        errorText = await response.text();
      } catch (error) {
        errorText = "";
      }

      summaryBox.textContent =
        `Summary endpoint failed: HTTP ${response.status}
` +
        `${errorText || "Check backend logs for details."}`;
      return;
    }

    const data = await response.json();
    summaryBox.textContent = formatStudySummary(data);
  } catch (error) {
    summaryBox.textContent = `Could not load summary: ${error.message}`;
  }
}

async function askHelper() {
  const prefix = getCode();
  const method = getMethod();
  const participantId = getParticipantId();
  const activeProblemId = getCurrentProblemId();

  document.getElementById("helperResponse").textContent = "Thinking...";

  try {
    const response = await fetch("/complete", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        prefix: prefix,
        method: method,
        problem_id: activeProblemId,
        participant_id: participantId,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      document.getElementById("helperResponse").textContent =
        data.detail || "Something went wrong.";
      return;
    }

    if (data.model) {
      activeModel = data.model;
    }

    const selectedOption =
      data.selected_option ||
      data.option_chosen ||
      data.optionChosen ||
      data.choice ||
      data.model_choice;

    lastSelectedOption = canonicalOption(selectedOption);
    showSelectedOption(lastSelectedOption);

    const suggestion = cleanSuggestionText(data.suggestion);

    if (lastSelectedOption === "direct_code" && suggestion) {
      setCode(suggestion);
      document.getElementById("helperResponse").textContent =
        "Code written into the editor.";
    } else if (suggestion) {
      document.getElementById("helperResponse").textContent = suggestion;
    } else {
      document.getElementById("helperResponse").textContent =
        "The helper returned an empty response. Try Ask Helper again.";
    }

    if (data.option_counts || data.option_total !== undefined) {
      const counts = normalizeCounts(data.option_counts || {});
      const totalFromCounts =
        counts.concept_suggestion +
        counts.code_suggestion +
        counts.direct_code;

      const total = Number.isFinite(Number(data.option_total))
        ? Number(data.option_total)
        : totalFromCounts;

      localOptionCounts = counts;
      showCounts(counts, total);
    } else {
      incrementLocalCount(lastSelectedOption);
      await refreshOptionCounts();
    }
  } catch (error) {
    document.getElementById("helperResponse").textContent =
      `Request failed: ${error.message}`;
  }
}

async function runTests() {
  const code = getCode();
  const method = getMethod();
  const participantId = getParticipantId();
  const activeProblemId = getCurrentProblemId();

  const response = await fetch("/submit", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      problem_id: activeProblemId,
      participant_id: participantId,
      method: method,
      selected_option: lastSelectedOption,
      code: code,
    }),
  });

  const data = await response.json();

  document.getElementById("testResults").textContent = JSON.stringify(
    data,
    null,
    2
  );

  await refreshOptionCounts();
  await refreshStudySummary();
}

window.askHelper = askHelper;
window.runTests = runTests;
window.resetCode = resetCode;
window.nextProblem = nextProblem;
window.previousProblem = previousProblem;
window.refreshStudySummary = refreshStudySummary;

require.config({
  paths: {
    vs: "https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/vs",
  },
});

require(["vs/editor/editor.main"], async function () {
  editor = monaco.editor.create(document.getElementById("editor"), {
    value: "",
    language: "python",
    theme: "vs-dark",
    fontSize: 15,
    minimap: {
      enabled: false,
    },
    automaticLayout: true,
    tabSize: 4,
    insertSpaces: true,
    wordWrap: "on",
    lineNumbers: "on",
    scrollBeyondLastLine: false,
  });

  const participantInput = document.getElementById("participantId");
  const methodSelect = document.getElementById("method");

  if (participantInput) {
    participantInput.addEventListener("input", function () {
      refreshOptionCounts();
      refreshStudySummary();
    });
  }

  if (methodSelect) {
    methodSelect.addEventListener("change", function () {
      refreshOptionCounts();
      refreshStudySummary();
    });
  }

  await loadActiveModel();
  await loadProblemIds();
  setupProblemControls();
  loadProblem();
});