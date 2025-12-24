(() => {
  const resultEl = document.getElementById('plotTwistResult');
  const metaEl = document.getElementById('plotTwistMeta');
  const rollButton = document.getElementById('plotTwistButton');

  if (!resultEl || !metaEl || !rollButton) return;

  function renderPlotTwist(data) {
    if (!data || !data.has_result) {
      resultEl.textContent = 'No plot twist rolled yet.';
      metaEl.textContent = '';
      return;
    }
    resultEl.textContent = data.result || 'No plot twist rolled yet.';
    const table = data.table ? `${data.table}` : 'Plot Twist';
    const roll = data.roll !== undefined ? `Roll ${data.roll}` : 'Roll ?';
    const stamp = data.timestamp ? data.timestamp : '';
    metaEl.textContent = `${table} · ${roll} · ${stamp}`;
  }

  async function fetchPlotTwist() {
    try {
      const response = await fetch('/plot_twist');
      if (!response.ok) return;
      const data = await response.json();
      renderPlotTwist(data);
    } catch (err) {
      resultEl.textContent = 'Unable to load plot twist.';
    }
  }

  async function rollPlotTwist() {
    try {
      const response = await fetch('/plot_twist/roll', { method: 'POST' });
      if (!response.ok) return;
      const data = await response.json();
      renderPlotTwist(data);
    } catch (err) {
      resultEl.textContent = 'Unable to roll a plot twist.';
    }
  }

  rollButton.addEventListener('click', rollPlotTwist);
  fetchPlotTwist();
  setInterval(fetchPlotTwist, 30000);
})();
