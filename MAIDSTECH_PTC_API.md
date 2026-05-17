# MaidsTech PTC API

Route-optimization and dispatch API for delivery, service, and moving operations. Every call below goes through `https://api.maidstech.ai`; tasks you create via this API are automatically optimized and assigned to the best worker in the associated team, then pushed to Onfleet for execution and tracking.

- **Base URL:** `https://api.maidstech.ai/v1`
- **Format:** JSON over HTTPS
- **Auth:** Bearer token in the `Authorization` header

---

## 1. Authentication

Every request requires a bearer token. Request a key from MaidsTech and send it on every call:

```http
Authorization: Bearer sk_live_YOUR_API_KEY
Content-Type: application/json
```

Requests without a valid key return **401 Unauthorized**.

---

## 2. Core concepts

| Resource | Description |
|---|---|
| **Task** | One delivery, pickup, cleaning job, or service visit. A task has a destination, a recipient, an optional time window, and belongs to a team. |
| **Worker** | A driver, cleaner, or technician who completes tasks. Workers have a vehicle type, a schedule, and belong to one or more teams. |
| **Team** | A group of workers that share a pool of tasks. Auto-optimization distributes a task to the best worker **within its team**. |
| **Route** | The ordered sequence of tasks that auto-optimization produces for each worker. |

When you create a task, the API:

1. Validates the task.
2. Runs the optimizer over all on-duty workers in the task's team.
3. Assigns the task to the best worker and slots it into their route.
4. Pushes the task to Onfleet so it shows up in the worker's app.

If the task cannot be assigned (no on-duty worker, no time overlap, etc.), it is returned in the response with `worker: null` and the reason in `unassignedReason` — you surface this to the operator; the task stays in the "Unassigned" column until a worker becomes eligible.

---

## 3. Endpoints

### 3.1 Create a task (auto-optimized)

```
POST /tasks
```

Creates a task and auto-assigns it to the best worker in the given team. This is the single call your dashboard needs to make.

**Request body**

```json
{
  "teamId": "nCx8AB3wQbGVmn8GFhu1vmkN",
  "destination": {
    "address": {
      "unparsed": "543 Howard St, San Francisco, CA 94105"
    }
  },
  "recipients": [
    {
      "name": "Jane Doe",
      "phone": "+14155550123",
      "notes": "Leave at door"
    }
  ],
  "completeAfter": 1745251200000,
  "completeBefore": 1745258400000,
  "serviceTime": 900,
  "quantity": 1,
  "notes": "2-bedroom cleaning, 2 hours",
  "autoAssign": true,
  "metadata": [
    { "name": "externalOrderId", "type": "string", "value": "ORD-48219" }
  ]
}
```

**Field reference**

| Field | Type | Required | Notes |
|---|---|---|---|
| `teamId` | string | **yes** | Team whose workers are eligible. Without this the optimizer has no pool and the task stays unassigned. |
| `destination` | object | **yes** | `address.unparsed` (single string) or `address.number/street/city/country` fields, or `location: [lng, lat]`. |
| `recipients` | array | **yes** | At least one recipient with `name` and `phone`. |
| `completeAfter` | integer (ms epoch) | recommended | Earliest time the task may be completed. |
| `completeBefore` | integer (ms epoch) | recommended | Latest time the task may be completed. Must be in the future. |
| `serviceTime` | integer (seconds) | recommended | How long the worker will spend on-site. Default `300`. Used by the optimizer to pack routes correctly. |
| `quantity` | integer | optional | Load units consumed. Default `1`. |
| `notes` | string | optional | Free-form notes shown to the worker. |
| `autoAssign` | boolean | optional | Default `true`. Set to `false` only if you want to leave the task unassigned intentionally. |
| `restrictedVehicleTypes` | array of strings | optional | Any of `CAR`, `TRUCK`, `BICYCLE`, `MOTORCYCLE`. Task will only go to workers whose vehicle matches. |
| `dependencies` | array of task IDs | optional | Task IDs this task depends on (e.g., delivery depends on pickup). |
| `pickupTask` | boolean | optional | `true` marks the task as a pickup. |
| `metadata` | array | optional | Arbitrary key/value pairs. Common use: your own order ID for reconciliation. |

**Response — success (201 Created, task assigned)**

```json
{
  "id": "2g4mQ6TKlaGSyHAA7NpVWPLs",
  "shortId": "c19eb52e",
  "state": 1,
  "teamId": "nCx8AB3wQbGVmn8GFhu1vmkN",
  "worker": "1LjhGUWdxFbvdsTdbyWb9Q~*",
  "etaSeconds": 1764,
  "estimatedArrivalTime": 1745252964000,
  "trackingURL": "https://onf.lt/c19eb52e",
  "destination": { "...": "..." },
  "recipients": [ { "...": "..." } ],
  "timeCreated": 1745251100000,
  "autoAssign": true,
  "unassignedReason": null
}
```

**Response — task created but could not be auto-assigned (201 Created, task unassigned)**

```json
{
  "id": "sUJK94d51kSOY~gYWaHoNoyT",
  "shortId": "f8a2b0c4",
  "state": 0,
  "teamId": "nCx8AB3wQbGVmn8GFhu1vmkN",
  "worker": null,
  "unassignedReason": "NO_ON_DUTY_WORKERS_IN_TEAM",
  "destination": { "...": "..." },
  "recipients": [ { "...": "..." } ],
  "timeCreated": 1745251100000,
  "autoAssign": true
}
```

`unassignedReason` values:

| Reason | What it means | Fix |
|---|---|---|
| `NO_ON_DUTY_WORKERS_IN_TEAM` | Nobody in the team is currently on-duty. | Ask the operator to put a worker on-duty. |
| `NO_TIME_WINDOW_OVERLAP` | `completeAfter`/`completeBefore` does not overlap any worker's shift. | Widen the task window, or put a worker on-duty during the window. |
| `NO_COMPATIBLE_VEHICLE` | `restrictedVehicleTypes` does not match any on-duty worker's vehicle. | Drop the restriction, or put a worker with the right vehicle on-duty. |
| `ALL_WORKERS_AT_CAPACITY` | Every eligible worker is already at `maxAssignedTaskCount`. | Raise the cap, add workers, or wait. |
| `DEPENDENCY_NOT_ASSIGNED` | A parent task in `dependencies` is not yet assigned. | Assign or remove the blocking dependency. |

The task is now live in your system; you can call `GET /tasks/{id}` to re-check it, or it will auto-assign on the next matching event (a worker goes on-duty, a task ahead of it completes, etc.).

---

### 3.2 Retrieve a task

```
GET /tasks/{taskId}
```

**Response**

```json
{
  "id": "2g4mQ6TKlaGSyHAA7NpVWPLs",
  "shortId": "c19eb52e",
  "state": 2,
  "teamId": "nCx8AB3wQbGVmn8GFhu1vmkN",
  "worker": "1LjhGUWdxFbvdsTdbyWb9Q~*",
  "etaSeconds": 612,
  "estimatedArrivalTime": 1745253576000,
  "trackingURL": "https://onf.lt/c19eb52e",
  "completionDetails": null,
  "timeCreated": 1745251100000,
  "timeLastModified": 1745252330000
}
```

`state` values:

| Value | Meaning |
|---|---|
| `0` | Unassigned |
| `1` | Assigned to a worker, not yet started |
| `2` | Active (worker is en route or on-site) |
| `3` | Completed |

---

### 3.3 Re-optimize existing tasks (optional)

```
POST /tasks/auto-assign
```

Use this only when you want to force-reoptimize tasks that were created with `autoAssign: false`, or tasks that got stuck in state `0` because no worker was on-duty when they were created.

**Request body**

```json
{
  "tasks": ["sUJK94d51kSOY~gYWaHoNoyT", "jNPQ6UEcpYZHS7vY3kQHwJ1L"],
  "teamId": "nCx8AB3wQbGVmn8GFhu1vmkN",
  "options": {
    "mode": "distance",
    "considerDependencies": true,
    "maxAssignedTaskCount": 50
  }
}
```

**Response**

```json
{
  "assigned": {
    "sUJK94d51kSOY~gYWaHoNoyT": "1LjhGUWdxFbvdsTdbyWb9Q~*"
  },
  "unassigned": ["jNPQ6UEcpYZHS7vY3kQHwJ1L"]
}
```

`mode` is `distance` (minimize total route distance) or `load` (balance task count across workers). Default is `distance`.

---

### 3.4 List workers

```
GET /workers?teamId={teamId}&onDuty=true
```

**Response**

```json
[
  {
    "id": "1LjhGUWdxFbvdsTdbyWb9Q~*",
    "name": "Alex Rivera",
    "phone": "+14155550199",
    "teams": ["nCx8AB3wQbGVmn8GFhu1vmkN"],
    "vehicle": { "type": "CAR", "description": "Prius" },
    "onDuty": true,
    "activeTask": "2g4mQ6TKlaGSyHAA7NpVWPLs",
    "tasksAssigned": 4
  }
]
```

---

### 3.5 List teams

```
GET /teams
```

**Response**

```json
[
  {
    "id": "nCx8AB3wQbGVmn8GFhu1vmkN",
    "name": "SF Downtown",
    "workers": ["1LjhGUWdxFbvdsTdbyWb9Q~*", "9aKxYqBc2dEfGhIjKlMnOpQr"],
    "hub": "Hy8dYrUlgv~wpBNZM9j48PuB"
  }
]
```

---

### 3.6 Update a task

```
PUT /tasks/{taskId}
```

Same body shape as `POST /tasks`; any fields you send overwrite the existing values. If you change `destination`, `completeAfter`, `completeBefore`, or `restrictedVehicleTypes`, the task is re-optimized automatically unless you pass `"autoAssign": false`.

---

### 3.7 Delete / cancel a task

```
DELETE /tasks/{taskId}
```

Removes the task from the worker's route and from Onfleet. Tasks in state `3` (completed) cannot be deleted.

---

## 4. Errors

Every error response has this shape:

```json
{
  "code": "validation_error",
  "message": "teamId is required",
  "details": { "field": "teamId" }
}
```

| HTTP | `code` | Meaning |
|---|---|---|
| 400 | `validation_error` | Body is malformed or a required field is missing. `details.field` points to the offending field. |
| 401 | `auth_invalid` | Missing or wrong `Authorization` header. |
| 403 | `permission_denied` | API key does not have access to the requested team or resource. |
| 404 | `not_found` | Task, worker, or team does not exist. |
| 409 | `conflict` | Task state does not allow the operation (e.g., deleting a completed task). |
| 422 | `cannot_assign` | Task was accepted but no worker is eligible. Same shape as the "unassigned" response in §3.1; task was created. |
| 429 | `rate_limited` | Too many requests. See §5. Retry after the `Retry-After` header. |
| 5xx | `internal_error` | Transient server error. Retry with exponential backoff. |

---

## 5. Rate limits

- **120 requests / minute** per API key
- **20 task creations / second** burst
- Responses include `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` headers
- 429 responses include `Retry-After` (seconds)

---

## 6. Webhooks (recommended)

Register a webhook URL in your MaidsTech dashboard to receive real-time updates instead of polling `GET /tasks/{id}`:

| Event | When it fires |
|---|---|
| `task.assigned` | Optimizer placed a previously unassigned task. |
| `task.started` | Worker marked the task as started. |
| `task.arrival` | Worker reached the destination. |
| `task.completed` | Worker completed the task (success or failure). |
| `task.unassigned` | Task moved back to unassigned (e.g., worker went off-duty). |

Webhook payload:

```json
{
  "event": "task.assigned",
  "timestamp": 1745252330000,
  "data": {
    "taskId": "sUJK94d51kSOY~gYWaHoNoyT",
    "workerId": "1LjhGUWdxFbvdsTdbyWb9Q~*",
    "teamId": "nCx8AB3wQbGVmn8GFhu1vmkN"
  }
}
```

Every webhook is signed with HMAC-SHA256 in the `X-MaidsTech-Signature` header using your webhook secret.

---

## 7. End-to-end example

**Create a task from the dashboard:**

```bash
curl -X POST https://api.maidstech.ai/v1/tasks \
  -H "Authorization: Bearer sk_live_YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "teamId": "nCx8AB3wQbGVmn8GFhu1vmkN",
    "destination": {
      "address": { "unparsed": "543 Howard St, San Francisco, CA 94105" }
    },
    "recipients": [
      { "name": "Jane Doe", "phone": "+14155550123" }
    ],
    "completeAfter": 1745251200000,
    "completeBefore": 1745258400000,
    "serviceTime": 900,
    "notes": "2-bedroom cleaning"
  }'
```

```javascript
const res = await fetch("https://api.maidstech.ai/v1/tasks", {
  method: "POST",
  headers: {
    Authorization: `Bearer ${process.env.MAIDSTECH_API_KEY}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    teamId: "nCx8AB3wQbGVmn8GFhu1vmkN",
    destination: { address: { unparsed: "543 Howard St, San Francisco, CA 94105" } },
    recipients: [{ name: "Jane Doe", phone: "+14155550123" }],
    completeAfter: Date.now() + 60 * 60 * 1000,
    completeBefore: Date.now() + 3 * 60 * 60 * 1000,
    serviceTime: 900,
    notes: "2-bedroom cleaning",
  }),
});

const task = await res.json();

if (task.worker) {
  // Task is auto-optimized and assigned — nothing else to do
  console.log(`Assigned to worker ${task.worker}, ETA ${task.etaSeconds}s`);
} else {
  // Task was created but could not be assigned right now — surface in UI
  console.warn(`Unassigned: ${task.unassignedReason}`);
}
```

---

## 8. Quick reference

| I want to… | Call |
|---|---|
| Create a task and have it auto-optimized | `POST /tasks` |
| Look up a task | `GET /tasks/{id}` |
| Retry optimization on stuck tasks | `POST /tasks/auto-assign` |
| Update a task's address or time window | `PUT /tasks/{id}` |
| Cancel a task | `DELETE /tasks/{id}` |
| See available workers in a team | `GET /workers?teamId={id}&onDuty=true` |
| List teams | `GET /teams` |

---

## 9. Support

- API reference (live): `https://api.maidstech.ai/docs`
- Status page: `https://status.maidstech.ai`
- Email: `support@maidstech.ai`
