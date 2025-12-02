// frontend/app.js
document.getElementById('analyzeBtn').addEventListener('click', async () => {
  const input = document.getElementById('imageInput');
  if (!input.files || input.files.length === 0) {
    alert('Choose an image first');
    return;
  }
  const file = input.files[0];
  const form = new FormData();
  form.append('image', file, file.name);

  const res = await fetch('/analyze', {
    method: 'POST',
    body: form
  });

  if (!res.ok) {
    const txt = await res.text();
    alert('Error: ' + txt);
    return;
  }
  const data = await res.json();
  const cl = data.classification;
  document.getElementById('result').style.display = 'block';
  document.getElementById('label').innerText = cl.label;
  document.getElementById('risk').innerText = 'Risk score: ' + cl.risk_score;
  document.getElementById('explanation').innerText = cl.explanation;
  document.getElementById('rawjson').innerText = JSON.stringify(data.gemini, null, 2);
});
