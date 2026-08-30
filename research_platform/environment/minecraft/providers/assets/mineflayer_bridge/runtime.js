'use strict'

const { Movements, goals: { GoalNear, GoalFollow } } = require('mineflayer-pathfinder')
const { Vec3 } = require('vec3')

let bot = null
let movements = null

function bindBot (value) {
  bot = value
  movements = null
}

function requireBot () {
  if (!bot || !bot.entity) throw new Error('bot not connected/spawned')
  return bot
}

function getBot () { return requireBot() }
function vec (value) { return value ? { x: Number(value.x), y: Number(value.y), z: Number(value.z) } : null }
function sleep (ms) { return new Promise(resolve => setTimeout(resolve, ms)) }

function stopMotion () {
  if (!bot) return
  try { if (bot.pathfinder && typeof bot.pathfinder.stop === 'function') bot.pathfinder.stop() } catch (_) {}
  try { if (bot.pvp && typeof bot.pvp.stop === 'function') bot.pvp.stop() } catch (_) {}
  try { if (typeof bot.stopDigging === 'function') bot.stopDigging() } catch (_) {}
  try { if (typeof bot.clearControlStates === 'function') bot.clearControlStates() } catch (_) {}
}

function actionTimeoutMs (msg, fallbackMs = 45000) {
  const raw = Number(msg && msg._action_timeout_ms)
  const budget = Number.isFinite(raw) && raw > 0 ? raw : fallbackMs
  return Math.max(500, Math.floor(budget * 0.95))
}

function remainingMs (deadlineMs, capMs) {
  const remaining = deadlineMs - Date.now()
  if (remaining <= 0) throw new Error('ACTION_DEADLINE_EXCEEDED')
  return Math.max(250, Math.min(remaining, capMs))
}

function withTimeout (promise, timeoutMs, label, onTimeout = stopMotion) {
  return new Promise((resolve, reject) => {
    let settled = false
    const timer = setTimeout(() => {
      if (settled) return
      settled = true
      try { if (onTimeout) onTimeout() } catch (_) {}
      const error = new Error(`${label}_TIMEOUT`)
      error.code = `${label}_TIMEOUT`
      reject(error)
    }, Math.max(1, timeoutMs))
    Promise.resolve(promise).then(value => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      resolve(value)
    }, error => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      reject(error)
    })
  })
}

function itemSummary (item) { return item ? { name: item.name, count: item.count, slot: item.slot } : null }

function matchName (name, query) {
  if (!query) return false
  const q = String(query).toLowerCase()
  const n = String(name || '').toLowerCase()
  if (q.startsWith('re:')) return new RegExp(q.slice(3)).test(n)
  return n === q || n.includes(q)
}

function entityMatches (entity, query) {
  return [entity.name, entity.username, entity.displayName, entity.type]
    .some(value => matchName(value, query))
}

function findEntity (query, maxDistance = 32, predicate = null) {
  const activeBot = requireBot()
  const candidates = Object.values(activeBot.entities || {})
    .filter(entity => entity && entity !== activeBot.entity && entity.position && entity.isValid !== false)
    .filter(entity => (!query || entityMatches(entity, query)) && (!predicate || predicate(entity)))
    .map(entity => ({ entity, distance: entity.position.distanceTo(activeBot.entity.position) }))
    .filter(candidate => candidate.distance <= maxDistance)
    .sort((left, right) => left.distance - right.distance)
  return candidates.length > 0 ? candidates[0].entity : null
}

function waitForPhysicsTicks (count = 10, timeoutMs = 2000) {
  const activeBot = requireBot()
  const target = Math.max(1, Number(count))
  return new Promise(resolve => {
    let ticks = 0
    let settled = false
    const finish = () => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      activeBot.removeListener('physicsTick', onTick)
      resolve()
    }
    const onTick = () => { if (++ticks >= target) finish() }
    const timer = setTimeout(finish, Math.max(1, timeoutMs))
    activeBot.on('physicsTick', onTick)
  })
}

async function waitForInventoryIncrease (name, before, timeoutMs = 2500) {
  const deadline = Date.now() + Math.max(1, timeoutMs)
  while (Date.now() < deadline) {
    const current = inventoryCount(name)
    if (current > before) return current - before
    await sleep(Math.min(100, Math.max(1, deadline - Date.now())))
  }
  return Math.max(0, inventoryCount(name) - before)
}

function inventoryCount (name) {
  const activeBot = requireBot()
  return activeBot.inventory.items()
    .filter(item => item.name === name)
    .reduce((total, item) => total + item.count, 0)
}

function inventoryMap () {
  const activeBot = requireBot()
  const out = {}
  for (const item of activeBot.inventory.items()) out[item.name] = (out[item.name] || 0) + item.count
  return out
}

function inventoryDelta (before, after) {
  const out = {}
  for (const name of new Set([...Object.keys(before), ...Object.keys(after)])) {
    const delta = Number(after[name] || 0) - Number(before[name] || 0)
    if (delta !== 0) out[name] = delta
  }
  return out
}

function isDroppedItemEntity (entity) {
  if (!entity || !entity.position || entity.isValid === false) return false
  if (typeof entity.getDroppedItem === 'function') {
    try { if (entity.getDroppedItem()) return true } catch (_) {}
  }
  const name = String(entity.name || '').toLowerCase()
  return name === 'item' || name === 'item_stack'
}

function droppedItemName (entity) {
  if (!isDroppedItemEntity(entity) || typeof entity.getDroppedItem !== 'function') return null
  try {
    const item = entity.getDroppedItem()
    return item && item.name ? String(item.name) : null
  } catch (_) {
    return null
  }
}

function itemDropExpectedNames (itemName) {
  const names = Array.isArray(itemName)
    ? itemName.map(String).filter(Boolean)
    : itemName ? [String(itemName)] : []
  return new Set(names)
}

function itemDropMatchesExpectedName (expectedNames, name) {
  return expectedNames.size === 0 || (name != null && expectedNames.has(name))
}

function itemDropAssociation (capture, entity) {
  const dropped = isDroppedItemEntity(entity)
  const distance = entity && entity.position ? entity.position.distanceTo(capture.center) : null
  return { dropped, distance, within: dropped && distance != null && distance <= capture.maxDistance }
}

function copyItemDropProtocolEntityFields (packet, data, name) {
  if (data && data.entityId != null) packet.entity_id = data.entityId
  if (data && data.collectedEntityId != null) packet.collected_entity_id = data.collectedEntityId
  if (data && data.collectorEntityId != null) packet.collector_entity_id = data.collectorEntityId
  if (data && data.pickupItemCount != null) packet.pickup_item_count = data.pickupItemCount
  if (data && data.type != null && name === 'spawn_entity') packet.entity_type = data.type
  if (data && Array.isArray(data.entityIds)) packet.entity_ids = data.entityIds.slice()
}

function copyItemDropProtocolPositionFields (packet, data) {
  if (data && data.x != null) packet.x = data.x
  if (data && data.y != null) packet.y = data.y
  if (data && data.z != null) packet.z = data.z
}

function copyItemDropProtocolInventoryFields (packet, data) {
  if (data && data.windowId != null) packet.window_id = data.windowId
  if (data && data.slot != null) packet.slot = data.slot
  if (data && Array.isArray(data.metadata)) packet.metadata_types = data.metadata.map(row => row.type)
  if (data && Array.isArray(data.items)) packet.item_slots = data.items.length
  if (data && data.item) packet.item_count = data.item.itemCount ?? data.item.count ?? null
}

function itemDropProtocolPacket (capture, data, metadata) {
  const name = metadata && metadata.name ? String(metadata.name) : ''
  if (!capture.tracedPacketNames.has(name)) return null
  const packet = { sequence: capture.protocolPackets.length + 1, packet: name }
  copyItemDropProtocolEntityFields(packet, data, name)
  copyItemDropProtocolPositionFields(packet, data)
  copyItemDropProtocolInventoryFields(packet, data)
  return packet
}

function recordItemDropProtocolPacket (capture, data, metadata) {
  const packet = itemDropProtocolPacket(capture, data, metadata)
  if (packet) capture.protocolPackets.push(packet)
}

function recordItemDropSpawn (capture, entity) {
  const row = itemDropAssociation(capture, entity)
  if (!row.dropped) return
  capture.spawnCandidates.push({
    entity_id: entity.id ?? null,
    item_name: droppedItemName(entity),
    position: vec(entity.position),
    distance_to_block_center: row.distance,
    matched: row.within
  })
  if (row.within && entity.id != null) capture.trackedEntities.set(entity.id, entity)
}

function itemDropCandidate (capture, entity) {
  const dropped = isDroppedItemEntity(entity)
  const observedName = dropped ? droppedItemName(entity) : null
  const distance = entity && entity.position ? entity.position.distanceTo(capture.center) : null
  const candidate = {
    entity_id: entity && entity.id != null ? entity.id : null,
    item_name: observedName,
    position: entity && entity.position ? vec(entity.position) : null,
    distance_to_block_center: distance,
    is_valid: Boolean(entity && entity.isValid !== false),
    matched: false,
    rejection: null
  }
  if (!dropped) candidate.rejection = 'NOT_DROPPED_ITEM_ENTITY'
  else if (distance == null || distance > capture.maxDistance) candidate.rejection = 'OUTSIDE_ASSOCIATION_RADIUS'
  else if (!itemDropMatchesExpectedName(capture.expectedNames, observedName)) candidate.rejection = 'ITEM_NAME_MISMATCH'
  else candidate.matched = true
  return { candidate, dropped, distance }
}

function recordItemDrop (capture, entity, finish) {
  const row = itemDropCandidate(capture, entity)
  capture.candidates.push(row.candidate)
  if (row.dropped && row.distance != null && row.distance <= capture.maxDistance && entity.id != null) {
    capture.trackedEntities.set(entity.id, entity)
  }
  if (row.candidate.matched) finish(entity)
}

function recordItemDropCollection (capture, collector, collected) {
  const own = Boolean(collector && capture.activeBot.entity && collector.id === capture.activeBot.entity.id)
  const tracked = Boolean(collected && collected.id != null && capture.trackedEntities.has(collected.id))
  if (!tracked) return
  capture.collectionCandidates.push({
    entity_id: collected.id,
    item_name: droppedItemName(collected),
    position: collected.position ? vec(collected.position) : null,
    own_collector: own,
    tracked: true
  })
  if (own) capture.collectedByBot.add(collected.id)
}

function attachItemDropCapture (capture, handlers) {
  if (capture.activeBot._client && typeof capture.activeBot._client.on === 'function') {
    capture.activeBot._client.on('packet', handlers.onProtocolPacket)
  }
  capture.activeBot.on('entitySpawn', handlers.onSpawn)
  capture.activeBot.on('itemDrop', handlers.onDrop)
  capture.activeBot.on('playerCollect', handlers.onCollect)
}

function cancelItemDropCapture (capture, handlers, finish) {
  capture.activeBot.removeListener('entitySpawn', handlers.onSpawn)
  capture.activeBot.removeListener('playerCollect', handlers.onCollect)
  if (capture.activeBot._client && typeof capture.activeBot._client.removeListener === 'function') {
    capture.activeBot._client.removeListener('packet', handlers.onProtocolPacket)
  }
  finish(null)
}

function itemDropPickupTarget (capture) {
  let nearest = null
  let nearestDistance = Infinity
  for (const entity of capture.trackedEntities.values()) {
    if (!entity || entity.isValid === false || capture.collectedByBot.has(entity.id)) continue
    const name = droppedItemName(entity)
    if (capture.expectedNames.size > 0 && name != null && !capture.expectedNames.has(name)) continue
    const distance = entity.position.distanceTo(capture.activeBot.entity.position)
    if (distance < nearestDistance) {
      nearest = entity
      nearestDistance = distance
    }
  }
  return nearest
}

function captureItemDropNear (position, itemName = null, maxDistance = 0.5) {
  const activeBot = requireBot()
  const blockPos = position instanceof Vec3 ? position : new Vec3(Number(position.x), Number(position.y), Number(position.z))
  // Mineflayer 4.37.1 emits entitySpawn from spawn_entity before itemDrop,
  // then itemDrop from entity_metadata carrying item_stack. Keep both stages
  // plus collection/protocol evidence until cancel so fast pickup stays observable.
  const capture = {
    activeBot,
    center: blockPos.offset(0.5, 0.5, 0.5),
    maxDistance,
    expectedNames: itemDropExpectedNames(itemName),
    candidates: [],
    spawnCandidates: [],
    collectionCandidates: [],
    trackedEntities: new Map(),
    collectedByBot: new Set(),
    protocolPackets: [],
    tracedPacketNames: new Set([
      'spawn_entity', 'entity_metadata', 'collect', 'set_slot',
      'window_items', 'entity_destroy', 'block_change'
    ])
  }
  let settled = false
  let resolvePromise
  const promise = new Promise(resolve => { resolvePromise = resolve })
  let handlers
  const finish = entity => {
    if (settled) return
    settled = true
    activeBot.removeListener('itemDrop', handlers.onDrop)
    resolvePromise(entity)
  }
  handlers = {
    onProtocolPacket: (data, metadata) => recordItemDropProtocolPacket(capture, data, metadata),
    onSpawn: entity => recordItemDropSpawn(capture, entity),
    onDrop: entity => recordItemDrop(capture, entity, finish),
    onCollect: (collector, collected) => recordItemDropCollection(capture, collector, collected)
  }
  attachItemDropCapture(capture, handlers)
  return {
    promise,
    cancel: () => cancelItemDropCapture(capture, handlers, finish),
    candidates: capture.candidates,
    spawn_candidates: capture.spawnCandidates,
    collection_candidates: capture.collectionCandidates,
    protocol_packets: capture.protocolPackets,
    pickupTarget: () => itemDropPickupTarget(capture),
    hasOwnCollection: () => capture.collectedByBot.size > 0
  }
}

function findNearbyDroppedItem (position, maxDistance = 6) {
  const activeBot = requireBot()
  const origin = position instanceof Vec3 ? position : new Vec3(Number(position.x), Number(position.y), Number(position.z))
  let nearest = null
  let nearestBotDistance = Infinity
  for (const entity of Object.values(activeBot.entities || {})) {
    if (entity === activeBot.entity || !isDroppedItemEntity(entity)) continue
    if (entity.position.distanceTo(origin) > maxDistance) continue
    const botDistance = entity.position.distanceTo(activeBot.entity.position)
    if (botDistance < nearestBotDistance) {
      nearest = entity
      nearestBotDistance = botDistance
    }
  }
  return nearest
}

function findInventoryItem (name) {
  return requireBot().inventory.items().find(item => item.name === name) || null
}

async function ensureMovements () {
  const activeBot = requireBot()
  if (!movements) movements = new Movements(activeBot)
  activeBot.pathfinder.setMovements(movements)
}

async function gotoEntity (entity, radius = 0, timeoutMs = 30000) {
  const activeBot = requireBot()
  if (!entity || entity.isValid === false || !entity.position) throw new Error('ENTITY_TARGET_INVALID')
  await ensureMovements()
  const boundedRadius = Math.max(0, Number(radius))
  await withTimeout(
    activeBot.pathfinder.goto(new GoalFollow(entity, boundedRadius)),
    timeoutMs,
    'PATHFINDER_FOLLOW'
  )
  const live = activeBot.entities && activeBot.entities[entity.id] ? activeBot.entities[entity.id] : entity
  return { entity_id: entity.id, position: vec(live.position), valid: live.isValid !== false }
}

function waitForOwnCollection (entity, timeoutMs = 5000) {
  const activeBot = requireBot()
  const targetId = entity && entity.id
  return new Promise(resolve => {
    let settled = false
    let timer = null
    const finish = value => {
      if (settled) return
      settled = true
      if (timer) clearTimeout(timer)
      activeBot.removeListener('playerCollect', onCollect)
      resolve(value)
    }
    const onCollect = (collector, collected) => {
      if (collector && collected && collector.id === activeBot.entity.id && collected.id === targetId) finish(true)
    }
    activeBot.on('playerCollect', onCollect)
    timer = setTimeout(() => finish(false), Math.max(1, timeoutMs))
  })
}

async function gotoPos (position, radius = 1.5, timeoutMs = 30000) {
  const activeBot = requireBot()
  await ensureMovements()
  const target = new Vec3(Number(position.x), Number(position.y), Number(position.z))
  const boundedRadius = Math.max(1, Number(radius))
  await withTimeout(
    activeBot.pathfinder.goto(
      new GoalNear(Math.floor(target.x), Math.floor(target.y), Math.floor(target.z), boundedRadius)
    ),
    timeoutMs,
    'PATHFINDER_GOTO'
  )
  const distance = activeBot.entity.position.distanceTo(target)
  return {
    target: vec(target),
    position: vec(activeBot.entity.position),
    distance,
    within_radius: distance <= Math.max(2.5, boundedRadius + 1)
  }
}

function result (tool, action, status, code, details = {}) {
  if (!['applied', 'partial', 'rejected'].includes(status)) throw new Error(`invalid action status ${status}`)
  return {
    action: { tool, ...action },
    outcome: { status, code, ...details },
    verified: status === 'applied'
  }
}

function applied (tool, action, code, details = {}) { return result(tool, action, 'applied', code, details) }
function partial (tool, action, code, details = {}) { return result(tool, action, 'partial', code, details) }
function rejected (tool, action, code, details = {}) { return result(tool, action, 'rejected', code, details) }

module.exports = {
  actionTimeoutMs,
  applied,
  bindBot,
  ensureMovements,
  entityMatches,
  findEntity,
  captureItemDropNear,
  droppedItemName,
  findInventoryItem,
  findNearbyDroppedItem,
  getBot,
  gotoEntity,
  gotoPos,
  inventoryCount,
  inventoryDelta,
  inventoryMap,
  isDroppedItemEntity,
  itemSummary,
  waitForInventoryIncrease,
  waitForOwnCollection,
  waitForPhysicsTicks,
  matchName,
  partial,
  remainingMs,
  rejected,
  requireBot,
  sleep,
  stopMotion,
  vec,
  withTimeout
}
