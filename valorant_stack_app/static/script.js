const playerNameInput = document.getElementById('player-name-input');
const addPlayerButton = document.getElementById('add-player-button');
const randomizeButton = document.getElementById('randomize-button');
const revealAllButton = document.getElementById('reveal-all-button');
const playerCountDisplay = document.getElementById('player-count');
const cardContainer = document.getElementById('player-card-container');
const alertContainer = document.getElementById('alert-container');
const selectedRoleTotalDisplay = document.getElementById('selected-role-total');

const roleInputs = {
    Duelist: document.getElementById('count-duelist'),
    Initiator: document.getElementById('count-initiator'),
    Controller: document.getElementById('count-controller'),
    Sentinel: document.getElementById('count-sentinel'),
};

let players = [];
let playerAgents = {};
let playerAssignedRoles = {};
let concealedPlayers = {};
let cachedAgentPool = [];
let nextPlayerId = 1;
let activeAlertType = '';
let activeAlertMessage = '';

const MAX_PLAYERS = 5;
const RANDOMIZE_DURATION = 3000;
const RANDOMIZE_MIN_INTERVAL = 70;
const RANDOMIZE_MAX_INTERVAL = 380;
const EMPTY_IMAGE = window.STATIC_EMPTY_IMAGE_URL || '/static/img/empty_image.png';
const HIDDEN_IMAGE = window.STATIC_HIDDEN_IMAGE_URL || '/static/img/hidden_image.jpg';

addPlayerButton.addEventListener('click', addPlayer);
randomizeButton.addEventListener('click', randomizeAgents);
revealAllButton.addEventListener('click', revealAllCards);
playerNameInput.addEventListener('input', handlePlayerNameInput);
playerNameInput.addEventListener('keypress', event => {
    if (event.key === 'Enter') {
        event.preventDefault();
        addPlayer();
    }
});

Object.values(roleInputs).forEach(input => {
    input.addEventListener('input', handleRoleCountChange);
});

function handlePlayerNameInput() {
    clearResolvedWarningAlert();
}

function addPlayer() {
    const playerName = playerNameInput.value.trim();

    if (!playerName) {
        showAlert('Please enter a player name.', 'warning');
        return;
    }

    if (players.length >= MAX_PLAYERS) {
        showAlert(`Maximum ${MAX_PLAYERS} players reached.`, 'warning');
        return;
    }

    players.push({ id: nextPlayerId++, name: playerName });
    playerNameInput.value = '';
    clearAlert();
    renderPlayerCards();
    clampRoleCountsToPlayerCount();
    updateRolePoolSummary();
}

function removePlayer(playerId) {
    const playerIndex = players.findIndex(player => player.id === playerId);
    if (playerIndex === -1) {
        return;
    }

    players.splice(playerIndex, 1);
    delete playerAgents[playerId];
    delete playerAssignedRoles[playerId];
    delete concealedPlayers[playerId];
    clearResolvedWarningAlert();
    renderPlayerCards();
    clampRoleCountsToPlayerCount();
    updateRolePoolSummary();
}

function handleRoleCountChange(event) {
    const input = event.target;
    const numericValue = Number.parseInt(input.value || '0', 10);
    if (!Number.isFinite(numericValue) || numericValue < 0) {
        input.value = '0';
    }

    if (Number.parseInt(input.value || '0', 10) > MAX_PLAYERS) {
        input.value = String(MAX_PLAYERS);
    }

    playerAssignedRoles = {};
    clampRoleCountsToPlayerCount();
    updateRolePoolSummary();
    clearResolvedWarningAlert();
}

function getSelectedRoleTotal() {
    return Object.values(roleInputs).reduce((sum, input) => {
        const value = Number.parseInt(input.value || '0', 10);
        return sum + (Number.isFinite(value) ? value : 0);
    }, 0);
}

function updateRolePoolSummary() {
    selectedRoleTotalDisplay.textContent = String(getSelectedRoleTotal());
}

function clampRoleCountsToPlayerCount() {
    const playerCount = players.length;
    const totalSelected = getSelectedRoleTotal();

    if (playerCount <= 0) {
        Object.values(roleInputs).forEach(input => {
            input.value = '0';
        });
        updateRolePoolSummary();
        return;
    }

    if (totalSelected <= playerCount) {
        return;
    }

    let overflow = totalSelected - playerCount;
    const priorityOrder = ['Sentinel', 'Controller', 'Initiator', 'Duelist'];

    for (const roleName of priorityOrder) {
        if (overflow <= 0) {
            break;
        }

        const input = roleInputs[roleName];
        let current = Number.parseInt(input.value || '0', 10);
        while (current > 0 && overflow > 0) {
            current -= 1;
            overflow -= 1;
        }
        input.value = String(current);
    }
    updateRolePoolSummary();
}

function buildRoleCountsPayload() {
    const payload = {};
    Object.entries(roleInputs).forEach(([roleName, input]) => {
        const value = Number.parseInt(input.value || '0', 10);
        if (Number.isFinite(value) && value > 0) {
            payload[roleName] = value;
        }
    });
    return payload;
}

function renderPlayerCards() {
    cardContainer.innerHTML = '';
    playerCountDisplay.textContent = players.length;

    players.forEach(player => {
        const assignedAgent = playerAgents[player.id] || null;
        createPlayerCard(player, assignedAgent);
    });

    updatePriorityBadges();

    randomizeButton.disabled = players.length === 0;
    updateRevealAllButton();
}

function updateRevealAllButton() {
    const hasConcealedCards = players.some(player => concealedPlayers[player.id] && playerAgents[player.id]);
    revealAllButton.disabled = !hasConcealedCards;
}

function randomizeAgents() {
    if (players.length === 0) {
        showAlert('Please add at least one player.', 'warning');
        return;
    }

    const selectedRoleTotal = getSelectedRoleTotal();
    if (selectedRoleTotal > players.length) {
        showAlert('Selected role counts cannot exceed the number of players.', 'warning');
        return;
    }

    randomizeButton.disabled = true;
    const roleCounts = buildRoleCountsPayload();

    Promise.all([
        fetch('/randomize_agents/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
            body: JSON.stringify({ players, roleCounts }),
        }).then(response => response.json().then(data => ({ ok: response.ok, data }))),
        loadAgentPool(),
    ])
        .then(([assignmentResponse, agentPool]) => {
            if (!assignmentResponse.ok) {
                showAlert(assignmentResponse.data.error || 'Failed to randomize agents.', 'danger');
                return;
            }

            if (!Array.isArray(agentPool) || agentPool.length === 0) {
                showAlert('Failed to load agents for animation.', 'danger');
                return;
            }

            cachedAgentPool = agentPool;
            playerAgents = {};
            playerAssignedRoles = {};
            concealedPlayers = {};

            assignmentResponse.data.assignments.forEach(assignment => {
                playerAgents[assignment.id] = assignment.agent;
                if (assignment.requiredRole) {
                    playerAssignedRoles[assignment.id] = assignment.requiredRole;
                }
                concealedPlayers[assignment.id] = true;
            });

            updatePriorityBadges();
            updateRevealAllButton();
            return animateRandomizedCards(agentPool);
        })
        .catch(error => {
            console.error('Error randomizing agents:', error);
            showAlert('Error randomizing agents.', 'danger');
        })
        .finally(() => {
            randomizeButton.disabled = players.length === 0;
        });
}

function loadAgentPool() {
    if (cachedAgentPool.length > 0) {
        return Promise.resolve(cachedAgentPool);
    }

    return fetch('/get_agents/')
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to fetch agent pool');
            }
            return response.json();
        })
        .then(agentPool => {
            if (!Array.isArray(agentPool)) {
                throw new Error('Invalid agent pool response');
            }

            cachedAgentPool = agentPool;
            return cachedAgentPool;
        });
}

function getRequiredRoleForPlayer(playerId) {
    const assignedRole = playerAssignedRoles[playerId] || '';
    if (assignedRole) {
        return assignedRole;
    }

    if (players.length !== 1) {
        return '';
    }

    const roleCounts = buildRoleCountsPayload();
    const selectedRoles = Object.keys(roleCounts);
    if (selectedRoles.length !== 1) {
        return '';
    }

    const selectedRole = selectedRoles[0];
    return roleCounts[selectedRole] === 1 ? selectedRole : '';
}

function getUniqueAlternatives(playerId, agentPool) {
    const requiredRole = getRequiredRoleForPlayer(playerId);

    const usedByOtherPlayers = new Set(
        Object.entries(playerAgents)
            .filter(([id, agent]) => Number(id) !== playerId && agent && agent.name)
            .map(([, agent]) => agent.name)
    );

    const currentAgentName = playerAgents[playerId] ? playerAgents[playerId].name : '';

    return agentPool.filter(agent => {
        if (!agent || !agent.name) {
            return false;
        }

        if (requiredRole && agent.role !== requiredRole) {
            return false;
        }

        return !usedByOtherPlayers.has(agent.name) && agent.name !== currentAgentName;
    });
}

function rerandomizeSingleCard(playerId) {
    const card = cardContainer.querySelector(`.player-card[data-player-id="${playerId}"]`);
    if (!card) {
        return;
    }

    const rerollButton = card.querySelector('.rerandomize-btn');
    if (rerollButton) {
        rerollButton.disabled = true;
    }

    loadAgentPool()
        .then(agentPool => {
            const requiredRole = getRequiredRoleForPlayer(playerId);
            const filteredPool = requiredRole
                ? agentPool.filter(agent => agent.role === requiredRole)
                : agentPool;

            const availableAlternatives = getUniqueAlternatives(playerId, filteredPool);
            if (availableAlternatives.length === 0) {
                showAlert('No unique alternative agent available for this card.', 'warning');
                return;
            }

            const finalAgent = availableAlternatives[Math.floor(Math.random() * availableAlternatives.length)];
            playerAgents[playerId] = finalAgent;
            if (requiredRole) {
                playerAssignedRoles[playerId] = requiredRole;
            }
            concealedPlayers[playerId] = true;
            updateRevealAllButton();
            card.classList.add('is-randomizing');

            return spinCardToAgent(card, availableAlternatives, finalAgent);
        })
        .catch(error => {
            console.error('Error re-randomizing card:', error);
            showAlert('Failed to re-randomize this card.', 'danger');
        })
        .finally(() => {
            if (rerollButton) {
                rerollButton.disabled = false;
            }
        });
}

function updatePriorityBadges() {
    players.forEach(player => {
        const card = cardContainer.querySelector(`.player-card[data-player-id="${player.id}"]`);
        if (!card) {
            return;
        }
        const badge = card.querySelector('.priority-badge');
        if (!badge) {
            return;
        }
        const requiredRole = playerAssignedRoles[player.id] || '';
        if (requiredRole) {
            badge.textContent = `★ ${requiredRole}`;
            badge.classList.add('is-visible');
        } else {
            badge.textContent = '';
            badge.classList.remove('is-visible');
        }
    });
}

function showAlert(message, type = 'warning') {
    activeAlertType = type;
    activeAlertMessage = message;
    alertContainer.innerHTML = `
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;
}

function clearAlert() {
    alertContainer.innerHTML = '';
    activeAlertType = '';
    activeAlertMessage = '';
}

function clearResolvedWarningAlert() {
    if (activeAlertType !== 'warning') {
        return;
    }

    const playerName = playerNameInput.value.trim();
    const selectedRoleTotal = getSelectedRoleTotal();

    if (activeAlertMessage === 'Please enter a player name.' && playerName.length > 0) {
        clearAlert();
        return;
    }

    if (activeAlertMessage === `Maximum ${MAX_PLAYERS} players reached.` && players.length < MAX_PLAYERS) {
        clearAlert();
        return;
    }

    if (activeAlertMessage === 'Please add at least one player.' && players.length > 0) {
        clearAlert();
        return;
    }

    if (activeAlertMessage === 'Selected role counts cannot exceed the number of players.' && selectedRoleTotal <= players.length) {
        clearAlert();
    }
}

function getCsrfToken() {
    const cookieValue = document.cookie
        .split('; ')
        .find(row => row.startsWith('csrftoken='));

    return cookieValue ? cookieValue.split('=')[1] : '';
}

function animateRandomizedCards(agentPool) {
    const cardElements = players
        .map(player => {
            const card = cardContainer.querySelector(`.player-card[data-player-id="${player.id}"]`);
            if (!card) {
                return null;
            }

            const requiredRole = playerAssignedRoles[player.id] || '';
            const filteredPool = requiredRole ? agentPool.filter(agent => agent.role === requiredRole) : agentPool;

            card.classList.add('is-randomizing');
            return { player, card, filteredPool: filteredPool.length ? filteredPool : agentPool };
        })
        .filter(Boolean);

    const animationPromises = cardElements.map(({ player, card, filteredPool }) => {
        const finalAgent = playerAgents[player.id];
        return spinCardToAgent(card, filteredPool, finalAgent);
    });

    return Promise.all(animationPromises);
}

function spinCardToAgent(card, agentPool, finalAgent) {
    if (!finalAgent) {
        card.classList.remove('is-randomizing');
        return Promise.resolve();
    }

    const startTime = performance.now();

    return new Promise(resolve => {
        function tick(now) {
            const elapsed = now - startTime;
            const progress = Math.min(elapsed / RANDOMIZE_DURATION, 1);

            if (progress >= 1) {
                updatePlayerCard(card, finalAgent);
                card.classList.remove('is-randomizing');
                resolve();
                return;
            }

            const randomAgent = agentPool[Math.floor(Math.random() * agentPool.length)];
            updatePlayerCard(card, randomAgent);

            const easedProgress = progress * progress;
            const nextDelay = RANDOMIZE_MIN_INTERVAL +
                (RANDOMIZE_MAX_INTERVAL - RANDOMIZE_MIN_INTERVAL) * easedProgress;

            window.setTimeout(() => {
                tick(performance.now());
            }, nextDelay);
        }

        tick(startTime);
    });
}

function updatePlayerCard(card, agent) {
    const playerId = Number(card.dataset.playerId);
    const agentImage = card.querySelector('.agent-image');
    const agentName = card.querySelector('.agent-name');

    const imageSrc = agent && agent.displayIcon ? agent.displayIcon : EMPTY_IMAGE;
    const hasAssignment = Boolean(agent && agent.name);
    const isConcealed = Boolean(hasAssignment && concealedPlayers[playerId]);

    card.classList.toggle('is-concealed', isConcealed);

    if (isConcealed) {
        agentImage.src = HIDDEN_IMAGE;
        agentImage.alt = 'Hidden assignment';
        agentImage.classList.add('is-empty');
        agentName.textContent = 'Click card to reveal';
        return;
    }

    agentImage.src = imageSrc;
    agentImage.alt = hasAssignment ? agent.name : 'Awaiting assignment';
    agentImage.classList.toggle('is-empty', !agent || !agent.displayIcon);
    agentName.textContent = hasAssignment ? agent.name : 'Awaiting random agent';
}

function revealPlayerCard(playerId) {
    if (!concealedPlayers[playerId] || !playerAgents[playerId]) {
        return;
    }

    concealedPlayers[playerId] = false;
    const card = cardContainer.querySelector(`.player-card[data-player-id="${playerId}"]`);
    if (!card) {
        return;
    }

    updatePlayerCard(card, playerAgents[playerId]);
    updateRevealAllButton();
}

function revealAllCards() {
    players.forEach(player => {
        if (!concealedPlayers[player.id] || !playerAgents[player.id]) {
            return;
        }

        concealedPlayers[player.id] = false;
        const card = cardContainer.querySelector(`.player-card[data-player-id="${player.id}"]`);
        if (!card) {
            return;
        }

        updatePlayerCard(card, playerAgents[player.id]);
    });

    updateRevealAllButton();
}

function createPlayerCard(player, agent = null) {
    const card = document.createElement('div');
    card.className = 'player-card';
    card.dataset.playerId = String(player.id);
    card.addEventListener('click', event => {
        if (event.target.closest('.remove-card-btn') || event.target.closest('.rerandomize-btn')) {
            return;
        }
        revealPlayerCard(player.id);
    });

    const removeButton = document.createElement('button');
    removeButton.type = 'button';
    removeButton.className = 'remove-card-btn';
    removeButton.textContent = 'X';
    removeButton.setAttribute('aria-label', `Remove ${player.name}`);
    removeButton.addEventListener('click', () => removePlayer(player.id));

    const agentImage = document.createElement('img');
    agentImage.src = EMPTY_IMAGE;
    agentImage.alt = 'Awaiting assignment';
    agentImage.className = 'agent-image';

    const cardContent = document.createElement('div');
    cardContent.className = 'card-content';

    const nameElement = document.createElement('h2');
    nameElement.textContent = player.name;

    const agentName = document.createElement('p');
    agentName.className = 'agent-name';
    agentName.textContent = 'Awaiting random agent';

    const rerandomizeButton = document.createElement('button');
    rerandomizeButton.type = 'button';
    rerandomizeButton.className = 'rerandomize-btn';
    rerandomizeButton.textContent = 'Randomize';
    rerandomizeButton.addEventListener('click', () => rerandomizeSingleCard(player.id));

    const priorityBadge = document.createElement('span');
    priorityBadge.className = 'priority-badge';
    priorityBadge.setAttribute('aria-label', 'Priority role assigned');

    cardContent.appendChild(nameElement);
    cardContent.appendChild(agentName);
    cardContent.appendChild(rerandomizeButton);

    card.appendChild(removeButton);
    card.appendChild(priorityBadge);
    card.appendChild(agentImage);
    card.appendChild(cardContent);

    if (agent) {
        updatePlayerCard(card, agent);
    } else {
        agentImage.classList.add('is-empty');
    }

    cardContainer.appendChild(card);

    return card;
}

updateRolePoolSummary();