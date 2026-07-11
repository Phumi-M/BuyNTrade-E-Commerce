(function () {
  const MAX_VIDEO_SECONDS = 5;
  const imagesInput = document.getElementById("images");
  const videoInput = document.getElementById("video");
  const thumbnailInput = document.getElementById("video-thumbnail-input");
  const imagesPreview = document.getElementById("images-preview");
  const videoPreview = document.getElementById("video-preview");
  const videoPlayer = document.getElementById("video-preview-player");
  const thumbnailPreview = document.getElementById("video-thumbnail-preview");
  const videoStatus = document.getElementById("video-status");
  const form = document.getElementById("create-listing-form");

  if (!form) {
    return;
  }

  function setThumbnailFile(blob) {
    const file = new File([blob], "video-thumbnail.jpg", { type: "image/jpeg" });
    const transfer = new DataTransfer();
    transfer.items.add(file);
    thumbnailInput.files = transfer.files;
  }

  function clearVideoSelection(message) {
    videoInput.value = "";
    thumbnailInput.value = "";
    videoPreview.hidden = true;
    if (videoPlayer.src) {
      URL.revokeObjectURL(videoPlayer.src);
      videoPlayer.removeAttribute("src");
    }
    thumbnailPreview.removeAttribute("src");
    videoStatus.textContent = message || "";
    videoStatus.classList.remove("video-status-error");
  }

  function canvasScore(ctx, width, height) {
    const data = ctx.getImageData(0, 0, width, height).data;
    let sum = 0;
    let sumSq = 0;
    const step = 4 * 8;
    let count = 0;

    for (let i = 0; i < data.length; i += step) {
      const value = data[i] * 0.299 + data[i + 1] * 0.587 + data[i + 2] * 0.114;
      sum += value;
      sumSq += value * value;
      count += 1;
    }

    const mean = sum / count;
    const variance = sumSq / count - mean * mean;
    return variance;
  }

  function captureFrame(video, time) {
    return new Promise((resolve, reject) => {
      const onSeeked = () => {
        video.removeEventListener("seeked", onSeeked);
        const canvas = document.createElement("canvas");
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        resolve({ canvas, score: canvasScore(ctx, canvas.width, canvas.height) });
      };

      video.addEventListener("seeked", onSeeked);
      video.addEventListener("error", () => reject(new Error("Could not read video frame.")), { once: true });
      video.currentTime = Math.min(Math.max(time, 0), Math.max(video.duration - 0.05, 0));
    });
  }

  async function processVideo(file) {
    const objectUrl = URL.createObjectURL(file);
    videoPlayer.src = objectUrl;
    videoPreview.hidden = false;
    videoStatus.textContent = "Analyzing video frames...";

    await new Promise((resolve, reject) => {
      videoPlayer.onloadedmetadata = resolve;
      videoPlayer.onerror = () => reject(new Error("Unsupported video format."));
    });

    if (videoPlayer.duration > MAX_VIDEO_SECONDS + 0.25) {
      clearVideoSelection(`Video must be ${MAX_VIDEO_SECONDS} seconds or less.`);
      videoStatus.classList.add("video-status-error");
      throw new Error("Video too long.");
    }

    const sampleTimes = [0.2, 0.5, 1, 2, 3, 4]
      .map((value) => Math.min(value, Math.max(videoPlayer.duration - 0.1, 0.1)))
      .filter((value, index, array) => array.indexOf(value) === index);

    const frames = [];
    for (const time of sampleTimes) {
      frames.push(await captureFrame(videoPlayer, time));
    }

    frames.sort((a, b) => b.score - a.score);
    const bestFrame = frames[0].canvas;

    const blob = await new Promise((resolve) => bestFrame.toBlob(resolve, "image/jpeg", 0.92));
    setThumbnailFile(blob);

    thumbnailPreview.src = bestFrame.toDataURL("image/jpeg", 0.92);
    videoPlayer.play();
    videoStatus.textContent = "Best frame selected for the listing thumbnail.";
  }

  imagesInput?.addEventListener("change", () => {
    if (!imagesPreview) {
      return;
    }
    const files = Array.from(imagesInput.files || []);
    if (!files.length) {
      imagesPreview.hidden = true;
      imagesPreview.innerHTML = "";
      return;
    }

    imagesPreview.innerHTML = "";
    files.slice(0, 8).forEach((file, index) => {
      const item = document.createElement("div");
      item.className = "gallery-upload-item";
      const img = document.createElement("img");
      img.src = URL.createObjectURL(file);
      img.alt = `Preview ${index + 1}`;
      const label = document.createElement("span");
      label.textContent = index === 0 ? "Cover" : `Photo ${index + 1}`;
      item.appendChild(img);
      item.appendChild(label);
      imagesPreview.appendChild(item);
    });
    imagesPreview.hidden = false;
  });

  videoInput?.addEventListener("change", async () => {
    const file = videoInput.files?.[0];
    if (!file) {
      clearVideoSelection("");
      return;
    }

    try {
      await processVideo(file);
    } catch (error) {
      if (!videoStatus.textContent) {
        clearVideoSelection(error.message || "Could not process video.");
      }
      videoStatus.classList.add("video-status-error");
    }
  });

  form.addEventListener("submit", (event) => {
    if (videoInput.files?.[0] && !thumbnailInput.files?.[0]) {
      event.preventDefault();
      videoStatus.textContent = "Wait for the video thumbnail to finish generating.";
      videoStatus.classList.add("video-status-error");
    }
  });
})();
