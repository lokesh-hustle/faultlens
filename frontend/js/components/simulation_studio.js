/**
 * FaultLens Frontend - Simulation Studio Component
 * Controls synthetic incident triggers and communicates with backend API.
 */

window.SimulationStudio = {
    init(onSimulationSuccess) {
        const btnTrigger = document.getElementById('btn-trigger-simulation');
        const feedbackEl = document.getElementById('sim-status-feedback');

        if (!btnTrigger) return;

        btnTrigger.addEventListener('click', async () => {
            const scenario = document.getElementById('sim-scenario-select').value;
            const userCount = parseInt(document.getElementById('sim-users-input').value, 10) || 50;
            const delaySec = parseFloat(document.getElementById('sim-delay-input').value) || 0.0;

            if (feedbackEl) {
                feedbackEl.classList.remove('hidden');
                feedbackEl.textContent = `Injecting fault scenario [${scenario}]... Running RCA isolation engine.`;
            }

            try {
                const response = await fetch('/api/v1/simulation/trigger', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        scenario: scenario,
                        user_count: userCount,
                        delay_seconds: delaySec
                    })
                });

                if (response.status === 429) {
                    const errData = await response.json();
                    if (feedbackEl) {
                        feedbackEl.style.color = '#ef4444';
                        feedbackEl.textContent = `🛡️ SECURITY DENIAL: ${errData.detail || 'Rate Limit Exceeded!'}`;
                    }
                    return;
                }

                const data = await response.json();

                if (feedbackEl) {
                    feedbackEl.style.color = '#10b981';
                    feedbackEl.textContent = `✔ Fault injected successfully. Isolated Origin: [${data.rca_report ? data.rca_report.root_cause_service : 'Active'}]`;
                }

                if (onSimulationSuccess && data.rca_report) {
                    onSimulationSuccess(data.rca_report);
                }
            } catch (err) {
                if (feedbackEl) {
                    feedbackEl.style.color = '#ef4444';
                    feedbackEl.textContent = `Failed to trigger scenario: ${err.message}`;
                }
            }
        });
    }
};
