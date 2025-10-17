const video = document.getElementById("video");
const canvas = document.getElementById("canvas");
const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");
const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const manualBtn = document.getElementById("manualBtn");

let stream = null;
let scanning = false;
let rafId = null;
let alreadyClaimed = false;

function setStatus(msg) {
  statusEl.textContent = msg;
}

async function claimNumber(qrData) {
  if (alreadyClaimed) return;
  alreadyClaimed = true;
  setStatus("กำลังขอเลขจากเซิร์ฟเวอร์...");

  try {
    const res = await fetch("/api/claim", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ qr_data: qrData || null }),
    });
    const data = await res.json();
    if (data.ok) {
      resultEl.style.display = "block";
      resultEl.textContent = data.code;
      setStatus("ได้เลขเรียบร้อย ✅");
    } else {
      setStatus("เกิดข้อผิดพลาด: " + data.error);
      alreadyClaimed = false;
    }
  } catch (err) {
    setStatus("เกิดข้อผิดพลาด: " + err.message);
    alreadyClaimed = false;
  }
}

async function startScan() {
  alreadyClaimed = false;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "environment" },
    });
    video.srcObject = stream;
    video.setAttribute("playsinline", true);
    await video.play();
    scanning = true;
    setStatus("กำลังสแกน QR...");
    tick();
  } catch (err) {
    setStatus("ไม่สามารถเปิดกล้องได้: " + err.message);
  }
}

function stopScan() {
  scanning = false;
  cancelAnimationFrame(rafId);
  if (stream) {
    stream.getTracks().forEach(t => t.stop());
    stream = null;
  }
  setStatus("หยุดสแกนแล้ว");
}

function tick() {
  if (!scanning) return;
  const w = video.videoWidth;
  const h = video.videoHeight;
  if (!w || !h) {
    rafId = requestAnimationFrame(tick);
    return;
  }
  const ctx = canvas.getContext("2d");
  canvas.width = w;
  canvas.height = h;
  ctx.drawImage(video, 0, 0, w, h);
  const img = ctx.getImageData(0, 0, w, h);
  const qr = jsQR(img.data, img.width, img.height);

  if (qr && qr.data) {
    setStatus("อ่าน QR ได้: " + qr.data);
    stopScan();
    claimNumber(qr.data);
  } else {
    rafId = requestAnimationFrame(tick);
  }
}

startBtn.addEventListener("click", startScan);
stopBtn.addEventListener("click", stopScan);
manualBtn.addEventListener("click", () => {
  stopScan();
  claimNumber(null);
});
