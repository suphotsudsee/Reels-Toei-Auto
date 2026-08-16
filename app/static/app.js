const form = document.querySelector("#job-form");
const topic = document.querySelector("#topic");
const submitButton = document.querySelector("#submit-button");
const emptyState = document.querySelector("#empty-state");
const jobState = document.querySelector("#job-state");
const resultState = document.querySelector("#result-state");
const retryButton = document.querySelector("#retry-button");
const errorBox = document.querySelector("#error-box");
const stageList = document.querySelector("#stage-list");
let pollTimer = null;
let currentJobId = null;

const stages = [
  ["research", "ค้นคว้าข้อมูล"], ["script", "เขียนสคริปต์"],
  ["broll", "เตรียม B-roll"], ["voice", "สร้างเสียงบรรยาย"],
  ["caption", "ทำคำบรรยาย"], ["render", "ตัดต่อวิดีโอ"],
  ["qc", "ตรวจคุณภาพ"], ["archive", "จัดเก็บผลงาน"]
];

topic.addEventListener("input", () => {
  document.querySelector("#topic-count").textContent = topic.value.length;
});

function showProgress() {
  emptyState.classList.add("hidden");
  resultState.classList.add("hidden");
  jobState.classList.remove("hidden");
}

function renderStages(activeStage, status) {
  const activeIndex = stages.findIndex(([key]) => key === activeStage);
  const completedCount = status === "completed" ? stages.length : Math.max(0, activeIndex);
  stageList.replaceChildren(...stages.map(([key, label], index) => {
    const item = document.createElement("div");
    item.className = `stage${index < completedCount ? " done" : ""}${key === activeStage ? " active" : ""}`;
    const icon = document.createElement("i");
    icon.textContent = index < completedCount ? "✓" : String(index + 1);
    const text = document.createElement("span");
    text.textContent = label;
    item.append(icon, text);
    return item;
  }));

  const percent = status === "completed" ? 100 : status === "queued" ? 3 : Math.max(8, Math.round(((activeIndex + .25) / stages.length) * 100));
  document.querySelector("#progress-percent").textContent = `${percent}%`;
  document.querySelector("#progress-bar").style.width = `${percent}%`;
}

function updateJob(job) {
  showProgress();
  currentJobId = job.id;
  localStorage.setItem("reels-current-job", job.id);
  renderStages(job.current_stage, job.status);
  errorBox.classList.add("hidden");
  retryButton.classList.add("hidden");

  const stageName = stages.find(([key]) => key === job.current_stage)?.[1];
  const labels = { queued: "งานอยู่ในคิว", running: stageName || "กำลังสร้างวิดีโอ", failed: "สร้างวิดีโอไม่สำเร็จ", completed: "วิดีโอพร้อมดาวน์โหลด" };
  document.querySelector("#status-label").textContent = labels[job.status] || job.status;
  document.querySelector("#status-copy").textContent = job.status === "completed" ? "เสร็จเรียบร้อยแล้ว" : `${labels[job.status] || "กำลังทำงาน"} กรุณารอสักครู่`;

  if (job.status === "failed") {
    clearTimeout(pollTimer);
    submitButton.disabled = false;
    errorBox.textContent = job.error || "เกิดข้อผิดพลาดที่ไม่ทราบสาเหตุ";
    errorBox.classList.remove("hidden");
    retryButton.classList.remove("hidden");
    return;
  }

  if (job.status === "completed") {
    clearTimeout(pollTimer);
    submitButton.disabled = false;
    localStorage.removeItem("reels-current-job");
    const videoUrl = `/jobs/${encodeURIComponent(job.id)}/video`;
    document.querySelector("#video-preview").src = videoUrl;
    document.querySelector("#download-button").href = videoUrl;
    jobState.classList.add("hidden");
    resultState.classList.remove("hidden");
  }
}

async function request(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try { detail = (await response.json()).detail || detail; } catch (_) { /* response was not JSON */ }
    throw new Error(detail);
  }
  return response.json();
}

async function pollJob(jobId) {
  try {
    const job = await request(`/jobs/${encodeURIComponent(jobId)}`);
    updateJob(job);
    if (["queued", "running"].includes(job.status)) {
      pollTimer = setTimeout(() => pollJob(jobId), 3000);
    }
  } catch (error) {
    document.querySelector("#status-copy").textContent = `ตรวจสอบสถานะไม่ได้: ${error.message}`;
    pollTimer = setTimeout(() => pollJob(jobId), 5000);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearTimeout(pollTimer);
  submitButton.disabled = true;
  document.querySelector("#status-copy").textContent = "กำลังส่งงานเข้าระบบ";
  showProgress();
  renderStages(null, "queued");
  try {
    const job = await request("/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        topic: topic.value.trim(),
        language: document.querySelector("#language").value,
        target_seconds: Number(document.querySelector("#duration").value)
      })
    });
    updateJob(job);
    pollTimer = setTimeout(() => pollJob(job.id), 2000);
  } catch (error) {
    submitButton.disabled = false;
    errorBox.textContent = `ส่งงานไม่สำเร็จ: ${error.message}`;
    errorBox.classList.remove("hidden");
  }
});

retryButton.addEventListener("click", async () => {
  if (!currentJobId) return;
  retryButton.disabled = true;
  try {
    const job = await request(`/jobs/${encodeURIComponent(currentJobId)}/retry`, { method: "POST" });
    updateJob(job);
    pollTimer = setTimeout(() => pollJob(job.id), 2000);
  } catch (error) {
    errorBox.textContent = `เริ่มใหม่ไม่สำเร็จ: ${error.message}`;
  } finally {
    retryButton.disabled = false;
  }
});

document.querySelector("#new-job-button").addEventListener("click", () => {
  document.querySelector("#video-preview").removeAttribute("src");
  resultState.classList.add("hidden");
  emptyState.classList.remove("hidden");
  document.querySelector("#status-copy").textContent = "พร้อมรับงานใหม่";
  topic.focus();
  window.scrollTo({ top: form.offsetTop, behavior: "smooth" });
});

const savedJobId = localStorage.getItem("reels-current-job");
if (savedJobId) {
  submitButton.disabled = true;
  pollJob(savedJobId);
}
