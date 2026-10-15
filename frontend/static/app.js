// Beyond Emergency Transfusion Management UI Logic

let activeTab = 'coordinator';
let currentMatchData = null;
let currentEventId = null;

// Tab Switching
function switchTab(tabId) {
  activeTab = tabId;
  const tabs = ['coordinator', 'caregiver', 'donor', 'simulation', 'admin'];
  tabs.forEach(t => {
    const btn = document.getElementById(`tab-${t}`);
    const view = document.getElementById(`view-${t}`);
    if (t === tabId) {
      btn.className = 'nav-tab px-3 py-1.5 rounded-lg bg-white text-slate-900 shadow-sm transition font-bold';
      view.classList.remove('hidden');
    } else {
      btn.className = 'nav-tab px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 transition font-medium';
      view.classList.add('hidden');
    }
  });

  if (tabId === 'coordinator') loadEvents();
  if (tabId === 'caregiver') populateCaregiverDropdown();
  if (tabId === 'donor') populateDonorDropdown();
  if (tabId === 'simulation') runSimulation();
  if (tabId === 'admin') { loadRules(); loadAuditLogs(); }
}

// 1. Coordinator Functions
async function loadEvents() {
  try {
    const res = await fetch('/api/events');
    const data = await res.json();
    const tbody = document.getElementById('events-table-body');
    tbody.innerHTML = '';

    document.getElementById('stat-events-count').innerText = data.total;

    data.events.forEach(ev => {
      const tr = document.createElement('tr');
      tr.className = 'hover:bg-slate-50 transition border-b border-slate-100';

      const isCovered = ev.coverage_count >= ev.units_required;
      const isAtRisk = ev.timeline.is_at_risk;

      let badgeClass = 'badge-partial';
      let statusLabel = `🟡 Partial (${ev.coverage_count}/${ev.units_required})`;
      if (isCovered) {
        badgeClass = 'badge-covered';
        statusLabel = `🟢 Covered (${ev.coverage_count}/${ev.units_required})`;
      } else if (isAtRisk) {
        badgeClass = 'badge-risk';
        statusLabel = `🔴 At Risk (${ev.coverage_count}/${ev.units_required})`;
      }

      tr.innerHTML = `
        <td class="py-3 px-6 font-mono text-xs">
          <div class="font-bold text-slate-900">${ev.planned_date}</div>
          <div class="text-slate-400">${ev.event_id}</div>
        </td>
        <td class="py-3 px-6">
          <span class="font-semibold text-slate-800">${ev.patient_pseudonym}</span>
          <div class="text-[11px] text-slate-400">${ev.centre_name}</div>
        </td>
        <td class="py-3 px-6">
          <span class="px-2 py-0.5 rounded font-black text-xs bg-rose-50 text-rose-700 border border-rose-200">${ev.blood_group}</span>
        </td>
        <td class="py-3 px-6 font-semibold text-slate-700">${ev.units_required} unit${ev.units_required > 1 ? 's' : ''}</td>
        <td class="py-3 px-6">
          <span class="px-2.5 py-1 rounded-full text-xs font-semibold ${badgeClass}">
            ${statusLabel}
          </span>
        </td>
        <td class="py-3 px-6 text-xs text-slate-600">
          <div class="font-medium">${ev.timeline.stage}</div>
          <div class="text-[11px] text-slate-400">${ev.timeline.days_until_event} days away</div>
        </td>
        <td class="py-3 px-6 text-right space-x-2">
          <button onclick="openDetailModal('${ev.event_id}')" class="px-2.5 py-1 text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg font-medium transition">
            Details
          </button>
          <button onclick="openMatchModal('${ev.event_id}')" class="px-3 py-1 text-xs bg-rose-600 hover:bg-rose-700 text-white rounded-lg font-medium shadow-sm transition">
            Match Donors
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Error loading events:', err);
  }
}

// Matching Modal Logic
async function openMatchModal(eventId) {
  try {
    currentEventId = eventId;
    const res = await fetch('/api/match', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event_id: eventId })
    });
    const matchData = await res.json();
    currentMatchData = matchData;

    document.getElementById('modal-match-subtitle').innerText = 
      `Matching for ${matchData.patient_id} (${matchData.recipient_group}) • ${matchData.eligible_candidates_count} qualified candidates found`;

    document.getElementById('modal-event-summary').innerHTML = `
      <div><strong>Target Event:</strong> ${eventId}</div>
      <div><strong>Recipient Group:</strong> ${matchData.recipient_group}</div>
      <div><strong>Required Units:</strong> ${matchData.units_required}</div>
      <div><strong>Primary Shortlist:</strong> ${matchData.primary_donors.length}</div>
      <div><strong>Backup Reserve:</strong> ${matchData.backup_donors.length}</div>
    `;

    // Render Primaries
    const primContainer = document.getElementById('modal-primary-candidates');
    primContainer.innerHTML = '';
    matchData.primary_donors.forEach((donor, idx) => {
      primContainer.appendChild(createCandidateCard(donor, 'Primary', idx + 1));
    });

    // Render Backups
    const backContainer = document.getElementById('modal-backup-candidates');
    backContainer.innerHTML = '';
    matchData.backup_donors.forEach((donor, idx) => {
      backContainer.appendChild(createCandidateCard(donor, 'Backup', idx + 1));
    });

    document.getElementById('modal-match').classList.remove('hidden');
  } catch (err) {
    alert('Error running matching console: ' + err.message);
  }
}

function createCandidateCard(c, role, rank) {
  const div = document.createElement('div');
  div.className = 'border border-slate-200 rounded-xl p-3 bg-white hover:border-slate-300 transition flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 text-xs';
  
  const b = c.breakdown || {};
  div.innerHTML = `
    <div class="space-y-1">
      <div class="flex items-center gap-2">
        <span class="font-bold text-slate-900">${rank}. ${c.donor_id}</span>
        <span class="px-2 py-0.5 rounded font-black text-rose-700 bg-rose-50 border border-rose-200">${c.donor_group}</span>
        ${c.is_panel_member ? '<span class="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-bold">Dedicated Panel</span>' : ''}
        <span class="text-slate-400">Distance: ${c.distance_km || 5} km</span>
      </div>
      <div class="text-slate-500 flex flex-wrap gap-x-3 text-[11px]">
        <span>ABO Match: <strong>${b.group_match || 'Identical'}</strong></span>
        <span>Phenotype: <strong>+${b.phenotype_match || 0}</strong></span>
        <span>Reliability: <strong>+${b.reliability || 0}</strong></span>
        <span>Proximity: <strong>+${b.proximity || 0}</strong></span>
        <span class="${b.scarcity_penalty < 0 ? 'text-amber-600 font-bold' : ''}">Scarcity Penalty: <strong>${b.scarcity_penalty || 0}</strong></span>
      </div>
    </div>
    <div class="flex items-center gap-3 self-end sm:self-center">
      <div class="text-right">
        <div class="text-xs text-slate-400">Match Score</div>
        <div class="text-lg font-black text-rose-600">${c.total_score}</div>
      </div>
    </div>
  `;
  return div;
}

function closeMatchModal() {
  document.getElementById('modal-match').classList.add('hidden');
}

async function dispatchInvitesFromModal() {
  if (!currentMatchData || !currentEventId) return;
  const primaryIds = currentMatchData.primary_donors.map(d => d.donor_id);
  const backupIds = currentMatchData.backup_donors.map(d => d.donor_id);

  try {
    const res = await fetch(`/api/dispatch-invites?event_id=${currentEventId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        primary_donor_ids: primaryIds,
        backup_donor_ids: backupIds
      })
    });
    alert(`Invitations dispatched to ${primaryIds.length} primary and ${backupIds.length} backup donors.`);
    closeMatchModal();
    loadEvents();
  } catch (err) {
    alert('Failed to dispatch invitations: ' + err.message);
  }
}

// Detail & Escalation Modal
async function openDetailModal(eventId) {
  try {
    const res = await fetch(`/api/events/${eventId}`);
    const data = await res.json();

    document.getElementById('modal-detail-title').innerText = `Event: ${eventId} (${data.event.planned_date})`;
    const body = document.getElementById('modal-detail-body');
    body.innerHTML = '';

    // Escalation warning if present
    if (data.escalation) {
      const esc = data.escalation;
      const escDiv = document.createElement('div');
      escDiv.className = 'p-4 rounded-xl bg-red-50 border border-red-200 text-red-900 space-y-2';
      escDiv.innerHTML = `
        <div class="flex items-center gap-2 font-bold text-red-700">
          <i class="fa-solid fa-triangle-exclamation"></i>
          <span>Escalation Active: ${esc.trigger} (Short by ${esc.units_short} unit${esc.units_short > 1 ? 's' : ''})</span>
        </div>
        <p class="text-xs">Immediate Protocol Recommended Actions:</p>
        <ul class="text-xs list-disc list-inside space-y-1">
          ${esc.recommended_actions.map(a => `<li>${a}</li>`).join('')}
        </ul>
      `;
      body.appendChild(escDiv);
    }

    // Invitations List
    const invDiv = document.createElement('div');
    invDiv.className = 'space-y-3';
    invDiv.innerHTML = `<h4 class="text-sm font-bold text-slate-800">Donor Invitation Roster (${data.invitations.length})</h4>`;

    if (data.invitations.length === 0) {
      invDiv.innerHTML += `<p class="text-xs text-slate-400 italic">No invitations created yet. Click "Match Donors" to allocate.</p>`;
    } else {
      data.invitations.forEach(inv => {
        const item = document.createElement('div');
        item.className = 'p-3 border border-slate-200 rounded-xl flex justify-between items-center text-xs';
        
        let statusBadge = 'bg-slate-100 text-slate-700';
        if (inv.status === 'ACCEPTED') statusBadge = 'bg-emerald-100 text-emerald-800 font-bold';
        if (inv.status === 'DECLINED') statusBadge = 'bg-red-100 text-red-800';

        item.innerHTML = `
          <div>
            <div class="font-bold text-slate-800">${inv.donor_id} (${inv.donor_blood_group}) • ${inv.role}</div>
            <div class="text-slate-400 text-[11px]">Sent: ${inv.sent_at} ${inv.responded_at ? '&bull; Responded: ' + inv.responded_at : ''}</div>
          </div>
          <div class="flex items-center gap-3">
            <span class="px-2.5 py-1 rounded-full ${statusBadge}">${inv.status}</span>
            ${inv.status === 'INVITED' ? `
              <button onclick="respondInvite('${inv.invite_id}', 'ACCEPT')" class="px-2 py-1 bg-emerald-600 text-white rounded text-[10px] font-bold">Simulate Accept</button>
              <button onclick="respondInvite('${inv.invite_id}', 'DECLINE')" class="px-2 py-1 bg-red-600 text-white rounded text-[10px] font-bold">Simulate Decline</button>
            ` : ''}
          </div>
        `;
        invDiv.appendChild(item);
      });
    }
    body.appendChild(invDiv);

    document.getElementById('modal-detail').classList.remove('hidden');
  } catch (err) {
    alert('Error fetching event details: ' + err.message);
  }
}

function closeDetailModal() {
  document.getElementById('modal-detail').classList.add('hidden');
}

async function respondInvite(inviteId, action) {
  try {
    await fetch('/api/invitations/respond', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        invite_id: inviteId,
        action: action,
        actor_id: 'DONOR-ACTION',
        role: 'DONOR'
      })
    });
    closeDetailModal();
    loadEvents();
  } catch (err) {
    alert('Error updating invite response: ' + err.message);
  }
}

// 2. Caregiver Functions
async function populateCaregiverDropdown() {
  try {
    const res = await fetch('/api/patients');
    const data = await res.json();
    const select = document.getElementById('cg-patient-select');
    select.innerHTML = '';
    data.patients.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.patient_id;
      opt.innerText = p.pseudonym;
      select.appendChild(opt);
    });
    if (data.patients.length > 0) {
      loadCaregiverView(data.patients[0].patient_id);
    }
  } catch (err) {
    console.error(err);
  }
}

async function loadCaregiverView(patientId) {
  try {
    const res = await fetch(`/api/caregiver/${patientId}`);
    const data = await res.json();

    document.getElementById('cg-patient-name').innerText = data.pseudonym;
    
    // Render Next Transfusion Banner
    const nextCard = document.getElementById('cg-next-card');
    if (data.next_event) {
      const n = data.next_event;
      const isConfirmed = n.is_fully_confirmed;
      nextCard.innerHTML = `
        <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <span class="text-xs font-bold uppercase tracking-wider text-slate-400">Next Scheduled Transfusion Session</span>
            <h3 class="text-2xl font-black text-slate-900 mt-1">${n.planned_date} <span class="text-sm font-semibold text-slate-500">(${n.days_away} days away)</span></h3>
            <p class="text-xs font-semibold ${isConfirmed ? 'text-emerald-700' : 'text-amber-700'} mt-1 flex items-center gap-1.5">
              <i class="fa-solid ${isConfirmed ? 'fa-circle-check text-emerald-600' : 'fa-clock text-amber-600'}"></i>
              ${n.status_message}
            </p>
          </div>
          <div class="p-4 bg-slate-50 rounded-xl border border-slate-100 text-center min-w-[160px]">
            <div class="text-xs text-slate-500 font-medium">Donor Coverage</div>
            <div class="text-2xl font-black ${isConfirmed ? 'text-emerald-600' : 'text-amber-600'}">${n.coverage_count} of ${n.units_required}</div>
            <div class="text-[10px] text-slate-400 mt-0.5">${isConfirmed ? 'Fully Prepared' : 'Shortlisting in progress'}</div>
          </div>
        </div>
      `;
    } else {
      nextCard.innerHTML = `<p class="text-slate-400 text-xs">No pending transfusions in the immediate calendar.</p>`;
    }

    // Render Timeline List
    const tList = document.getElementById('cg-timeline-list');
    tList.innerHTML = '';
    data.upcoming_schedule.forEach(ev => {
      const div = document.createElement('div');
      div.className = 'p-3 border border-slate-100 rounded-xl flex justify-between items-center bg-slate-50 text-xs';
      div.innerHTML = `
        <div class="space-y-0.5">
          <div class="font-bold text-slate-800">${ev.planned_date}</div>
          <div class="text-slate-500">${ev.units_required} unit${ev.units_required > 1 ? 's' : ''} blood &bull; Interval: ${data.interval_days} days</div>
        </div>
        <div>
          <span class="px-2.5 py-1 rounded-full text-[11px] font-semibold ${ev.coverage_count >= ev.units_required ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-700'}">
            ${ev.coverage_count >= ev.units_required ? 'Confirmed' : 'Planned'}
          </span>
        </div>
      `;
      tList.appendChild(div);
    });

  } catch (err) {
    console.error(err);
  }
}

// 3. Donor Portal Functions
async function populateDonorDropdown() {
  try {
    const res = await fetch('/api/donors?limit=15');
    const data = await res.json();
    const select = document.getElementById('donor-select');
    select.innerHTML = '';
    data.donors.forEach(d => {
      const opt = document.createElement('option');
      opt.value = d.donor_id;
      opt.innerText = `${d.donor_id} (${d.abo}${d.rh})`;
      select.appendChild(opt);
    });
    if (data.donors.length > 0) {
      loadDonorPortal(data.donors[1] ? data.donors[1].donor_id : data.donors[0].donor_id);
    }
  } catch (err) {
    console.error(err);
  }
}

async function loadDonorPortal(donorId) {
  try {
    const res = await fetch(`/api/donor-portal/${donorId}`);
    const data = await res.json();
    const d = data.donor;

    document.getElementById('donor-portal-name').innerText = `${donorId}`;
    document.getElementById('donor-bg-badge').innerText = `${d.abo}${d.rh}`;
    document.getElementById('donor-elig-status').innerText = data.is_currently_eligible ? 'ELIGIBLE' : 'DEFERRED / IN GAP';
    document.getElementById('donor-elig-status').className = `px-2.5 py-1 text-xs font-bold rounded-full ${data.is_currently_eligible ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`;
    document.getElementById('donor-elig-date').innerText = `Eligible from: ${data.eligible_from}`;
    document.getElementById('donor-elig-reason').innerText = data.eligibility_reason;
    document.getElementById('donor-showup-rate').innerText = `${Math.round(d.show_up_rate * 100)}%`;

    // Phenotype
    const p = d.phenotype_json || {};
    document.getElementById('donor-pheno-badge').innerText = `Rh: C(${p.C || '?'}) c(${p.c || '?'}) E(${p.E || '?'}) e(${p.e || '?'}) Kell(${p.K || '?'})`;

    // Invitations
    const list = document.getElementById('donor-invites-list');
    list.innerHTML = '';

    if (data.invitations.length === 0) {
      list.innerHTML = `<p class="text-xs text-slate-400 italic">No pending requests at this time. Thank you for your readiness!</p>`;
    } else {
      data.invitations.forEach(inv => {
        const item = document.createElement('div');
        item.className = 'border border-slate-200 rounded-xl p-4 bg-slate-50 space-y-3 text-xs';
        item.innerHTML = `
          <div class="flex justify-between items-start">
            <div>
              <span class="px-2 py-0.5 rounded text-[10px] font-bold ${inv.role === 'PRIMARY' ? 'bg-emerald-100 text-emerald-800' : 'bg-indigo-100 text-indigo-800'}">${inv.role} INVITATION</span>
              <div class="font-bold text-slate-900 text-sm mt-1">Transfusion Need on ${inv.planned_date}</div>
              <div class="text-slate-500 text-[11px]">${inv.centre_name}</div>
            </div>
            <span class="px-2.5 py-1 rounded-full font-bold text-xs ${inv.status === 'ACCEPTED' ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-700'}">${inv.status}</span>
          </div>
          <div class="p-3 bg-white border border-slate-200 rounded-lg text-slate-700 italic">
            "${inv.anonymized_message}"
          </div>
          <div class="flex justify-end gap-2 pt-1">
            ${inv.status === 'INVITED' ? `
              <button onclick="donorRespond('${inv.invite_id}', 'ACCEPT', '${donorId}')" class="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-bold shadow-sm transition">
                <i class="fa-solid fa-check mr-1"></i> Accept Request
              </button>
              <button onclick="donorRespond('${inv.invite_id}', 'DECLINE', '${donorId}')" class="px-4 py-1.5 border border-slate-300 hover:bg-slate-100 text-slate-700 rounded-lg font-bold transition">
                <i class="fa-solid fa-xmark mr-1"></i> Decline
              </button>
            ` : `<span class="text-slate-400 font-medium">Response recorded: ${inv.status}</span>`}
          </div>
        `;
        list.appendChild(item);
      });
    }

  } catch (err) {
    console.error(err);
  }
}

async function donorRespond(inviteId, action, donorId) {
  try {
    await fetch('/api/invitations/respond', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        invite_id: inviteId,
        action: action,
        actor_id: donorId,
        role: 'DONOR'
      })
    });
    alert(`Thank you! Request was marked as: ${action}`);
    loadDonorPortal(donorId);
  } catch (err) {
    alert('Error submitting response: ' + err.message);
  }
}

// 4. Simulation Functions
async function runSimulation() {
  const btn = document.getElementById('btn-run-sim');
  btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Running simulation...`;
  try {
    const res = await fetch('/api/simulation/evaluate?months=6');
    const data = await res.json();
    btn.innerHTML = `<i class="fa-solid fa-play text-purple-600"></i> Run 6-Month Simulation`;

    const metrics = data.metrics_comparison;
    const grid = document.getElementById('sim-metrics-grid');
    grid.innerHTML = '';

    const cards = [
      {
        title: metrics.t3_confirmed_coverage_rate.label,
        proactive: metrics.t3_confirmed_coverage_rate.proactive,
        reactive: metrics.t3_confirmed_coverage_rate.reactive,
        diff: metrics.t3_confirmed_coverage_rate.difference,
        icon: 'fa-calendar-check',
        color: 'emerald'
      },
      {
        title: metrics.avg_confirmation_lead_time_days.label,
        proactive: metrics.avg_confirmation_lead_time_days.proactive,
        reactive: metrics.avg_confirmation_lead_time_days.reactive,
        diff: metrics.avg_confirmation_lead_time_days.difference,
        icon: 'fa-stopwatch',
        color: 'blue'
      },
      {
        title: metrics.last_minute_scrambles.label,
        proactive: metrics.last_minute_scrambles.proactive,
        reactive: metrics.last_minute_scrambles.reactive,
        diff: metrics.last_minute_scrambles.difference,
        icon: 'fa-triangle-exclamation',
        color: 'rose'
      },
      {
        title: metrics.escalations_per_100_transfusions.label,
        proactive: metrics.escalations_per_100_transfusions.proactive,
        reactive: metrics.escalations_per_100_transfusions.reactive,
        diff: metrics.escalations_per_100_transfusions.difference,
        icon: 'fa-shield-halved',
        color: 'purple'
      }
    ];

    cards.forEach(c => {
      const div = document.createElement('div');
      div.className = 'bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-2';
      div.innerHTML = `
        <div class="flex justify-between items-center">
          <p class="text-xs font-bold text-slate-500 uppercase">${c.title}</p>
          <i class="fa-solid ${c.icon} text-${c.color}-600"></i>
        </div>
        <div class="flex items-baseline justify-between mt-1">
          <div>
            <div class="text-2xl font-black text-emerald-600">${c.proactive}</div>
            <div class="text-[11px] text-slate-400">Proactive Engine</div>
          </div>
          <div class="text-right">
            <div class="text-lg font-bold text-slate-400">${c.reactive}</div>
            <div class="text-[11px] text-slate-400">Reactive Baseline</div>
          </div>
        </div>
        <div class="text-xs font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-md border border-emerald-100 flex items-center justify-between">
          <span>Advantage</span>
          <span>${c.diff}</span>
        </div>
      `;
      grid.appendChild(div);
    });

    // Render monthly comparison bars
    const barBox = document.getElementById('sim-monthly-bars');
    barBox.innerHTML = '';
    data.monthly_trend.forEach(m => {
      const item = document.createElement('div');
      item.className = 'space-y-1';
      item.innerHTML = `
        <div class="flex justify-between text-xs font-semibold text-slate-700">
          <span>${m.month} (${m.events_count} Transfusion Sessions)</span>
          <span>Proactive: ${m.proactive_coverage_pct}% vs Reactive: ${m.reactive_coverage_pct}%</span>
        </div>
        <div class="w-full bg-slate-100 h-4 rounded-full overflow-hidden flex">
          <div class="bg-emerald-500 h-full transition-all duration-500" style="width: ${m.proactive_coverage_pct}%"></div>
          <div class="bg-amber-400 h-full opacity-60" style="width: ${Math.max(0, 100 - m.proactive_coverage_pct)}%"></div>
        </div>
      `;
      barBox.appendChild(item);
    });

  } catch (err) {
    alert('Simulation error: ' + err.message);
  }
}

// 5. Admin & Audit
async function loadRules() {
  try {
    const res = await fetch('/api/admin/rules');
    const rules = await res.json();
    document.getElementById('rule-male-interval').value = rules.male_interval_days;
    document.getElementById('rule-female-interval').value = rules.female_interval_days;
    document.getElementById('rule-min-age').value = rules.min_age;
    document.getElementById('rule-max-age').value = rules.max_age;
    document.getElementById('rule-min-weight').value = rules.min_weight_kg;
  } catch (err) {
    console.error(err);
  }
}

async function saveRules(e) {
  e.preventDefault();
  try {
    const payload = {
      male_interval_days: parseInt(document.getElementById('rule-male-interval').value),
      female_interval_days: parseInt(document.getElementById('rule-female-interval').value),
      min_age: parseInt(document.getElementById('rule-min-age').value),
      max_age: parseInt(document.getElementById('rule-max-age').value),
      min_weight_kg: parseFloat(document.getElementById('rule-min-weight').value)
    };
    await fetch('/api/admin/rules', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    alert('National eligibility rules updated successfully and audit logged!');
    loadAuditLogs();
  } catch (err) {
    alert('Error saving rules: ' + err.message);
  }
}

async function requestRevealPII() {
  const entityId = document.getElementById('pii-entity-id').value;
  const reason = document.getElementById('pii-reason').value;
  if (!reason) {
    alert('Audit reason is strictly mandatory under DPDP compliance rules.');
    return;
  }
  try {
    const res = await fetch('/api/privacy/reveal-pii', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        entity_id: entityId,
        actor_id: 'COORDINATOR-01',
        role: 'COORDINATOR',
        reason: reason
      })
    });
    const data = await res.json();
    const box = document.getElementById('pii-result-box');
    box.classList.remove('hidden');
    box.innerHTML = `
      <div class="font-bold text-slate-900 border-b pb-1">Decrypted PII for ${entityId}</div>
      ${Object.entries(data.pii).map(([k, v]) => `<div><strong>${k}:</strong> ${v}</div>`).join('')}
      <div class="text-[10px] text-emerald-600 font-semibold pt-1">Access verified & logged into immutable audit repository.</div>
    `;
    loadAuditLogs();
  } catch (err) {
    alert('PII reveal denied: ' + err.message);
  }
}

async function loadAuditLogs() {
  try {
    const res = await fetch('/api/privacy/audit-logs');
    const data = await res.json();
    const tbody = document.getElementById('audit-table-body');
    tbody.innerHTML = '';
    data.logs.forEach(l => {
      const tr = document.createElement('tr');
      tr.className = 'hover:bg-slate-50 transition border-b border-slate-100';
      tr.innerHTML = `
        <td class="py-2.5 px-4 font-bold text-slate-800">${l.log_id}</td>
        <td class="py-2.5 px-4 text-slate-500">${l.timestamp.slice(0, 19)}</td>
        <td class="py-2.5 px-4"><span class="px-2 py-0.5 rounded bg-slate-100 text-slate-800 font-semibold">${l.actor_id}</span> <span class="text-[10px] text-slate-400">(${l.role})</span></td>
        <td class="py-2.5 px-4 font-bold ${l.action.includes('PII') ? 'text-amber-700' : 'text-slate-800'}">${l.action}</td>
        <td class="py-2.5 px-4 text-slate-600">${l.entity}: ${l.entity_id}</td>
        <td class="py-2.5 px-4 text-slate-500 max-w-xs truncate" title="${l.reason}">${l.reason}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error(err);
  }
}

// Initial Boot
document.addEventListener('DOMContentLoaded', () => {
  loadEvents();
});
