let state = {
  operation: null,
  fileId: null,
  fileName: null,
  fileSize: null,
  fileExt: null,
  downloadUrl: null,
  expiresAt: null,
  countdownTimer: null,
};

function selectOp(op) {
  state.operation = op;
  document.querySelectorAll('.card').forEach(c => c.classList.remove('active'));
  document.querySelector(`[data-op="${op}"]`).classList.add('active');

  document.getElementById('uploadHint').textContent =
    op === 'compress' ? '支持 PDF 格式，最大 10MB' : '支持 PDF、DOCX 格式，最大 10MB';
  document.getElementById('fileInput').accept =
    op === 'compress' ? '.pdf' : '.pdf,.docx';

  document.getElementById('optionsPanel').style.display = 'none';
  document.getElementById('resultPanel').style.display = 'none';
  document.getElementById('uploadZone').style.display = 'block';
}

// Upload zone
const uploadZone = document.getElementById('uploadZone');
const uploadInner = document.getElementById('uploadInner');
const fileInput = document.getElementById('fileInput');

uploadInner.addEventListener('click', () => fileInput.click());

uploadInner.addEventListener('dragover', (e) => {
  e.preventDefault();
  uploadInner.classList.add('dragover');
});
uploadInner.addEventListener('dragleave', () => {
  uploadInner.classList.remove('dragover');
});
uploadInner.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadInner.classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file) handleFile(file);
});

fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) handleFile(fileInput.files[0]);
});

async function handleFile(file) {
  const ext = '.' + file.name.split('.').pop().toLowerCase();
  if (state.operation === 'compress' && ext !== '.pdf') {
    showError('压缩功能仅支持 PDF 文件');
    return;
  }
  if (!['.pdf', '.docx'].includes(ext)) {
    showError('仅支持 PDF 和 DOCX 格式');
    return;
  }

  const formData = new FormData();
  formData.append('file', file);

  try {
    const resp = await fetch('/api/upload', { method: 'POST', body: formData });
    if (!resp.ok) {
      const err = await resp.json();
      showError(err.detail || '上传失败');
      return;
    }
    const data = await resp.json();
    state.fileId = data.file_id;
    state.fileName = data.filename;
    state.fileSize = data.size;
    state.fileExt = data.extension;
    state.expiresAt = data.expires_at;

    showOptions(data);
  } catch (e) {
    showError('网络错误，请检查连接');
  }
}

function showOptions(data) {
  const sizeStr = data.size > 1024 * 1024
    ? (data.size / (1024 * 1024)).toFixed(1) + ' MB'
    : (data.size / 1024).toFixed(0) + ' KB';

  document.getElementById('fileInfo').innerHTML = `
    <span>${data.filename}</span>
    <span style="color:#64748b;font-size:12px">${sizeStr}</span>
  `;

  document.getElementById('compressOptions').style.display =
    state.operation === 'compress' ? 'block' : 'none';

  document.getElementById('btnText').textContent =
    state.operation === 'compress' ? '开始压缩' : '开始转换';

  document.getElementById('resultPanel').style.display = 'none';
  document.getElementById('optionsPanel').style.display = 'block';
}

const levelDescs = {
  light: '轻度模式 - 轻微压缩，保持高质量，适合保存用',
  balanced: '均衡模式 - 在体积和质量之间取得平衡，推荐',
  maximum: '最大模式 - 尽可能缩小体积，适合网络传输',
};

function setLevel(level) {
  document.getElementById('levelDesc').textContent = levelDescs[level];
}

async function processFile() {
  const btn = document.getElementById('processBtn');
  btn.disabled = true;
  document.getElementById('btnText').textContent = '处理中...';
  document.getElementById('spinner').style.display = 'inline-block';

  try {
    let resp;
    if (state.operation === 'compress') {
      const level = document.querySelector('input[name="level"]:checked').value;
      resp = await fetch(`/api/compress/${state.fileId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `level=${level}`,
      });
    } else {
      const target = state.operation === 'pdf2word' ? 'docx' : 'pdf';
      resp = await fetch(`/api/convert/${state.fileId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `target_format=${target}`,
      });
    }

    if (!resp.ok) {
      const err = await resp.json();
      showError(err.detail || '处理失败');
      resetBtnState();
      return;
    }

    const data = await resp.json();
    showResult(data);
  } catch (e) {
    showError('网络错误，请检查连接');
    resetBtnState();
  }
}

function showResult(data) {
  document.getElementById('optionsPanel').style.display = 'none';
  document.getElementById('resultPanel').style.display = 'block';

  state.downloadUrl = data.download_url;
  state.expiresAt = data.expires_at;

  let detailsHtml = '';

  if (data.ratio !== undefined) {
    const origMB = (data.original_size / (1024 * 1024)).toFixed(1);
    const compMB = (data.compressed_size / (1024 * 1024)).toFixed(1);
    const saved = (data.original_size - data.compressed_size) / (1024 * 1024);
    detailsHtml = `
      原始大小：${origMB} MB<br>
      压缩后：${compMB} MB<br>
      <strong>缩小了 ${data.ratio}%（节省 ${saved.toFixed(1)} MB）</strong>
    `;
  } else {
    detailsHtml = '文件转换完成，点击下方按钮下载';
  }

  document.getElementById('resultDetails').innerHTML = detailsHtml;
  document.getElementById('resultTitle').textContent =
    data.ratio !== undefined ? '压缩完成' : '转换完成';

  const downloadBtn = document.getElementById('downloadBtn');
  downloadBtn.href = data.download_url;

  const ext = data.download_url.split('.').pop();
  const opLabel = state.operation === 'compress' ? 'compressed' :
    state.operation === 'pdf2word' ? 'converted' : 'converted';
  downloadBtn.download = `${opLabel}.${ext}`;

  startCountdown(data.expires_at);
}

function startCountdown(expiresAt) {
  if (state.countdownTimer) clearInterval(state.countdownTimer);

  function tick() {
    const now = new Date();
    const end = new Date(expiresAt);
    const diff = Math.max(0, end - now);
    const minutes = Math.floor(diff / 60000);
    const seconds = Math.floor((diff % 60000) / 1000);

    document.getElementById('countdown').textContent =
      diff > 0
        ? `文件将在 ${minutes} 分 ${seconds} 秒后自动删除`
        : '文件已过期';
  }

  tick();
  state.countdownTimer = setInterval(tick, 1000);
}

function resetAll() {
  if (state.countdownTimer) clearInterval(state.countdownTimer);
  state = { operation: null, fileId: null, countdownTimer: null };
  document.querySelectorAll('.card').forEach(c => c.classList.remove('active'));
  document.getElementById('uploadZone').style.display = 'none';
  document.getElementById('optionsPanel').style.display = 'none';
  document.getElementById('resultPanel').style.display = 'none';
  document.getElementById('fileInput').value = '';
  resetBtnState();
}

function resetBtnState() {
  const btn = document.getElementById('processBtn');
  btn.disabled = false;
  document.getElementById('btnText').textContent = '开始处理';
  document.getElementById('spinner').style.display = 'none';
}

function showError(msg) {
  const toast = document.getElementById('errorToast');
  document.getElementById('errorMsg').textContent = msg;
  toast.style.display = 'block';
  setTimeout(() => { toast.style.display = 'none'; }, 4000);
}
