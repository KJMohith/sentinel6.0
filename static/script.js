const fileInput = document.getElementById("videoInput");
const fileName = document.getElementById("fileName");
const statusBox = document.getElementById("status");
const resultSection = document.getElementById("result");
const processBtn = document.getElementById("processBtn");

fileInput.addEventListener("change", () => {
  fileName.textContent = fileInput.files.length ? `📄 ${fileInput.files[0].name}` : "No file selected";
});

processBtn.addEventListener("click", uploadVideo);

function assignSlot(platform, url) {
  const slot = resultSection.querySelector(`[data-platform='${platform}']`);
  if (!slot || !url) return;

  const video = slot.querySelector("video");
  const downloadBtn = slot.querySelector(".download-btn");

  video.src = url;
  downloadBtn.href = url;
}

function assignYoutubeOutput(type, url) {
  const block = resultSection.querySelector(`[data-youtube-type='${type}']`);
  if (!block || !url) return;

  const video = block.querySelector("video");
  const downloadBtn = block.querySelector(".download-btn");

  video.src = url;
  downloadBtn.href = url;
}

function assignYoutubeSlots(outputs) {
  const shortUrl =
    outputs.youtube_short ||
    outputs.youtube_shorts ||
    outputs.youtubeSmall ||
    outputs.youtube_small ||
    outputs.youtube ||
    (outputs.youtube_outputs && outputs.youtube_outputs.short) ||
    null;

  const longUrl =
    outputs.youtube_long_subtitled ||
    outputs.youtube_subtitled ||
    outputs.youtubeLong ||
    outputs.youtube_long ||
    (outputs.youtube_outputs && outputs.youtube_outputs.long_subtitled) ||
    null;

  assignYoutubeOutput("short", shortUrl);
  assignYoutubeOutput("long", longUrl || shortUrl);
}

function isHiddenSegment(url) {
  const lower = (url || "").toLowerCase();
  return lower.includes("start.mp4") || lower.includes("mid.mp4") || lower.includes("middle.mp4") || lower.includes("end.mp4");
}

function hasHiddenSegments(outputs) {
  return Object.values(outputs || {}).some((value) => {
    if (typeof value === "string") return isHiddenSegment(value);
    if (value && typeof value === "object") {
      return Object.values(value).some((nested) => typeof nested === "string" && isHiddenSegment(nested));
    }
    return false;
  });
}

async function uploadVideo() {
  if (!fileInput.files.length) {
    statusBox.textContent = "⚠ Please choose a video first.";
    return;
  }

  const formData = new FormData();
  formData.append("video", fileInput.files[0]);

  statusBox.textContent = "⏳ Uploading and processing video...";
  resultSection.classList.add("hidden");

  try {
    const response = await fetch("/upload", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();
    if (!response.ok || !data.success) {
      throw new Error(data.error || "Processing failed.");
    }

    const outputs = data.outputs || {};
    if (hasHiddenSegments(outputs)) {
      throw new Error("Internal segment output detected. Only final videos are allowed.");
    }

    assignSlot("instagram", outputs.instagram);
    assignSlot("x", outputs.x);
    assignYoutubeSlots(outputs);

    statusBox.textContent = "✅ Done! Download your platform outputs below.";
    resultSection.classList.remove("hidden");
  } catch (error) {
    statusBox.textContent = `❌ ${error.message}`;
  }
}
