const $ = (id) => document.getElementById(id);

function esc(v) {
    return String(v ?? '').replace(/[&<>"']/g, c => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[c]));
}

async function loadData() {
    try {
        const [s, r] = await Promise.all([
            fetch('/api/reports/summary'),
            fetch('/api/requests?limit=12')
        ]);

        if (!s.ok || !r.ok) {
            throw new Error('Não foi possível consultar a API.');
        }

        const summary = await s.json();
        const rows = await r.json();

        $('total').textContent = summary.total;
        $('recent').textContent = summary.last_24h;
        $('critical').textContent = summary.priority_1_count;
        $('llm').textContent = Math.round(summary.llm_share * 100) + '%';

        $('requests').innerHTML = rows.length
            ? rows.map(x => `
                <article class="item">
                    <div class="item-head">
                        <div>
                            <h3>#${x.id} · ${esc(x.subject)}</h3>
                            <p>${esc(x.summary)}</p>
                        </div>

                        <span class="tag ${x.urgency === 'critica' ? 'critical' : ''}">
                            ${esc(x.urgency)}
                        </span>
                    </div>

                    <div class="item-meta">
                        <span>${esc(x.protocol)}</span>
                        <span>· ${esc(x.department)}</span>
                        <span>· ${esc(x.status)}</span>
                        <span>· ${x.used_llm ? 'Anthropic' : 'modo local'}</span>
                    </div>

                    <div class="item-actions">
                        <button
                            type="button"
                            class="delete-btn"
                            data-delete-id="${x.id}">
                            Excluir
                        </button>
                    </div>
                </article>
            `).join('')
            : '<p class="hint">Nenhuma solicitação registrada ainda.</p>';

    } catch (e) {
        $('requests').innerHTML = `<p class="hint">${esc(e.message)}</p>`;
    }
}

// Exclusão individual de solicitações
$('requests').addEventListener('click', async (event) => {
    const button = event.target.closest('[data-delete-id]');

    if (!button) return;

    const id = button.dataset.deleteId;

    if (!confirm(`Deseja realmente excluir a solicitação #${id}? Esta ação não poderá ser desfeita.`)) {
        return;
    }

    const token = prompt('Informe seu token administrativo:');

    if (token === null) return;

    if (!token.trim()) {
        $('feedback').textContent = 'Token administrativo não informado.';
        return;
    }

    button.disabled = true;

    try {
        const response = await fetch(`/api/requests/${id}`, {
            method: 'DELETE',
            headers: {
                'X-Admin-Token': token.trim()
            }
        });

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            throw new Error(data.detail || 'Não foi possível excluir a solicitação.');
        }

        $('feedback').textContent = `Solicitação #${id} excluída com sucesso.`;

        await loadData();

    } catch (error) {
        $('feedback').textContent = 'Falha ao excluir: ' + error.message;
        button.disabled = false;
    }
});

// Cadastro de novas solicitações
$('request-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const b = $('submit');
    b.disabled = true;
    b.textContent = 'Processando...';

    $('feedback').textContent = 'Os quatro agentes estão processando a solicitação.';

    try {
        const r = await fetch('/api/requests?source=form', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name: $('name').value,
                email: $('email').value,
                subject: $('subject').value,
                message: $('message').value
            })
        });

        const data = await r.json();

        if (!r.ok) {
            throw new Error(
                data.detail?.[0]?.msg ||
                data.detail ||
                'Erro ao processar.'
            );
        }

        $('feedback').textContent =
            `Protocolo ${data.protocol} criado. Categoria: ${data.category}; destino: ${data.department}; modo LLM: ${data.used_llm ? 'sim' : 'não'}.`;

        $('subject').value = '';
        $('message').value = '';

        await loadData();

    } catch (err) {
        $('feedback').textContent = 'Falha: ' + err.message;

    } finally {
        b.disabled = false;
        b.textContent = '✦ Processar solicitação';
    }
});

loadData();