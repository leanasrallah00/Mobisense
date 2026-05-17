# MaidsTech PTC API — Reference

This document lists the public APIs exposed by MaidsTech PTC. External
dashboards and integrations call these endpoints to create and manage
tasks, workers, and teams. Task auto-optimization is triggered
automatically when the correct fields are provided in the request body
(see **Auto-Optimization** below).

---

## Base URL

```
https://api.maidstech.ai/v1
```

## Authentication

Every request must include your API key as a bearer token:

```http
Authorization: Bearer <YOUR_API_KEY>
Content-Type: application/json
```

Keys are issued by MaidsTech and are scoped per organization.

## Conventions

- All request and response bodies are JSON.
- All timestamps are ISO-8601 in UTC (e.g. `2026-04-21T17:30:00Z`).
- All IDs are opaque strings.
- `200 OK` = success; `201 Created` = resource created; `4xx` =
  client error; `5xx` = server error.

---

## Auto-Optimization

Tasks are auto-assigned to the best available worker **on creation**
when the request includes **all** of the following:

| Field | Why it's required |
|---|---|
| `teamId` | Defines the pool of workers eligible to receive the task. |
| `autoAssign` set to `true` | Opts the task into the optimizer. Without it, the task is created in the **Unassigned** column and stays there. |
| `destination` | Required to compute routing distance. |
| `completeAfter` / `completeBefore` | Time window the optimizer uses to match worker schedules. |

If any of these is missing, the task is still created successfully but
**will not be auto-assigned**. The API returns `201` in both cases; the
response body's `worker` field is `null` when the task was not
assigned.

---

## Endpoints

### Tasks

#### `POST /tasks` — Create a task

Creates a task and (if `autoAssign=true` and a valid team exists)
automatically assigns it to the best worker.

**Request:**

```json
{
  "teamId": "wIFp5l~GOFVpGqV3yHyw6Gbl",
  "autoAssign": true,
  "destination": {
    "address": "123 Palm St, Jeddah, Saudi Arabia",
    "location": [39.1925, 21.4858]
  },
  "recipient": {
    "name": "Sara Al-Ghamdi",
    "phone": "+966500000000",
    "notes": "Gate code 4421"
  },
  "completeAfter": "2026-04-22T08:00:00Z",
  "completeBefore": "2026-04-22T12:00:00Z",
  "serviceTime": 15,
  "quantity": 1,
  "notes": "Leave at reception if no answer.",
  "metadata": [
    { "name": "orderId", "type": "string", "value": "ORD-8842" }
  ]
}
```

**Response (`201 Created`):**

```json
{
  "id": "2g4mQ6TKlaGSyHAA7NpVWPLs",
  "teamId": "wIFp5l~GOFVpGqV3yHyw6Gbl",
  "worker": "1LjhGUWdxFbvdsTdbyWb9Q~*",
  "state": "assigned",
  "autoAssigned": true,
  "destination": { "address": "123 Palm St, Jeddah, Saudi Arabia", "location": [39.1925, 21.4858] },
  "recipient": { "name": "Sara Al-Ghamdi", "phone": "+966500000000" },
  "completeAfter": "2026-04-22T08:00:00Z",
  "completeBefore": "2026-04-22T12:00:00Z",
  "estimatedArrivalTime": "2026-04-22T09:12:00Z",
  "createdAt": "2026-04-21T17:30:00Z"
}
```

When no eligible worker is available, `worker` is `null`, `state` is
`"unassigned"`, and `autoAssigned` is `false`. Everything else is
returned the same way.

#### `POST /tasks/batch` — Create many tasks in one call

Up to 100 tasks per request. Optimization runs across the full batch,
so batching gives better routes than creating tasks one by one.

**Request:**

```json
{
  "autoAssign": true,
  "teamId": "wIFp5l~GOFVpGqV3yHyw6Gbl",
  "tasks": [
    { "destination": { "address": "123 Palm St, Jeddah" }, "recipient": { "name": "A", "phone": "+966500000001" }, "completeAfter": "2026-04-22T08:00:00Z", "completeBefore": "2026-04-22T12:00:00Z" },
    { "destination": { "address": "45 Corniche Rd, Jeddah" }, "recipient": { "name": "B", "phone": "+966500000002" }, "completeAfter": "2026-04-22T08:00:00Z", "completeBefore": "2026-04-22T12:00:00Z" }
  ]
}
```

**Response (`201 Created`):**

```json
{
  "created": [
    { "id": "2g4mQ6TKlaGSyHAA7NpVWPLs", "worker": "1LjhGUWdxFbvdsTdbyWb9Q~*", "state": "assigned" },
    { "id": "sUJK94d51kSOY~gYWaHoNoyT", "worker": null, "state": "unassigned" }
  ],
  "assignedCount": 1,
  "unassignedCount": 1
}
```

#### `GET /tasks/{id}` — Retrieve one task

Returns the full task object, including the currently assigned worker
and ETA.

**Response (`200 OK`):**

```json
{
  "id": "2g4mQ6TKlaGSyHAA7NpVWPLs",
  "teamId": "wIFp5l~GOFVpGqV3yHyw6Gbl",
  "worker": "1LjhGUWdxFbvdsTdbyWb9Q~*",
  "state": "assigned",
  "destination": { "address": "123 Palm St, Jeddah", "location": [39.1925, 21.4858] },
  "completeAfter": "2026-04-22T08:00:00Z",
  "completeBefore": "2026-04-22T12:00:00Z",
  "estimatedArrivalTime": "2026-04-22T09:12:00Z",
  "createdAt": "2026-04-21T17:30:00Z",
  "updatedAt": "2026-04-21T17:30:05Z"
}
```

#### `GET /tasks` — List tasks

**Query parameters:**

| Name | Type | Description |
|---|---|---|
| `teamId` | string | Filter by team. |
| `worker` | string | Filter by assigned worker. |
| `state` | string | `unassigned`, `assigned`, `active`, `completed`, `failed`. |
| `from` | ISO-8601 | Include tasks created at or after this time. |
| `to` | ISO-8601 | Include tasks created at or before this time. |
| `limit` | int | Page size (default `50`, max `200`). |
| `cursor` | string | Pagination cursor returned by the previous page. |

**Response (`200 OK`):**

```json
{
  "tasks": [
    { "id": "2g4mQ6TKlaGSyHAA7NpVWPLs", "state": "assigned", "worker": "1LjhGUWdxFbvdsTdbyWb9Q~*" }
  ],
  "nextCursor": "eyJvZmZzZXQiOjUwfQ=="
}
```

#### `PUT /tasks/{id}` — Update a task

Any subset of the fields below can be sent. If the task is already
assigned and you change `completeBefore`, the worker is recomputed
automatically.

**Request:**

```json
{
  "completeAfter": "2026-04-22T09:00:00Z",
  "completeBefore": "2026-04-22T13:00:00Z",
  "notes": "Updated per customer request."
}
```

**Response (`200 OK`):** the full updated task object.

#### `POST /tasks/{id}/assign` — Manually assign a task

Forces the task onto a specific worker, bypassing the optimizer. Use
only when an operator needs to override.

**Request:**

```json
{ "worker": "1LjhGUWdxFbvdsTdbyWb9Q~*" }
```

**Response (`200 OK`):** the updated task with `worker` set.

#### `POST /tasks/{id}/unassign` — Release a task

Moves the task back to the **Unassigned** column. Useful before
cancellation or manual re-routing.

**Response (`200 OK`):** the updated task with `worker: null` and `state: "unassigned"`.

#### `POST /tasks/reoptimize` — Re-run the optimizer

Re-optimizes a set of tasks or an entire team. Call this when workers
go on-duty, shifts change, or a stuck task needs another try.

**Request:**

```json
{ "teamId": "wIFp5l~GOFVpGqV3yHyw6Gbl" }
```

or

```json
{ "taskIds": ["2g4mQ6TKlaGSyHAA7NpVWPLs", "sUJK94d51kSOY~gYWaHoNoyT"] }
```

**Response (`200 OK`):**

```json
{
  "assigned": { "2g4mQ6TKlaGSyHAA7NpVWPLs": "1LjhGUWdxFbvdsTdbyWb9Q~*" },
  "unassigned": ["sUJK94d51kSOY~gYWaHoNoyT"]
}
```

#### `DELETE /tasks/{id}` — Delete a task

Permanently removes the task. Completed tasks cannot be deleted.

**Response:** `204 No Content`.

---

### Workers

#### `GET /workers` — List workers

**Query parameters:**

| Name | Type | Description |
|---|---|---|
| `teamId` | string | Filter by team. |
| `onDuty` | boolean | `true` returns only workers currently on shift. |

**Response (`200 OK`):**

```json
{
  "workers": [
    {
      "id": "1LjhGUWdxFbvdsTdbyWb9Q~*",
      "name": "Omar Khaled",
      "phone": "+966500000099",
      "teams": ["wIFp5l~GOFVpGqV3yHyw6Gbl"],
      "vehicle": { "type": "CAR", "description": "Toyota Hilux", "licensePlate": "JED-4821" },
      "onDuty": true,
      "location": [39.1807, 21.4761],
      "activeTask": "2g4mQ6TKlaGSyHAA7NpVWPLs"
    }
  ]
}
```

#### `POST /workers` — Create a worker

**Request:**

```json
{
  "name": "Omar Khaled",
  "phone": "+966500000099",
  "teams": ["wIFp5l~GOFVpGqV3yHyw6Gbl"],
  "vehicle": { "type": "CAR", "description": "Toyota Hilux", "licensePlate": "JED-4821" }
}
```

**Response (`201 Created`):** the worker object.

#### `GET /workers/{id}` — Retrieve a worker

Returns the worker object including current location and active task.

#### `PUT /workers/{id}` — Update a worker

Any subset of the creation fields can be sent.

#### `DELETE /workers/{id}` — Remove a worker

**Response:** `204 No Content`.

---

### Teams

#### `GET /teams` — List teams

**Response (`200 OK`):**

```json
{
  "teams": [
    {
      "id": "wIFp5l~GOFVpGqV3yHyw6Gbl",
      "name": "Jeddah Central",
      "workerCount": 12,
      "hub": "hub_01"
    }
  ]
}
```

#### `POST /teams` — Create a team

**Request:**

```json
{ "name": "Jeddah Central", "hub": "hub_01" }
```

**Response (`201 Created`):** the team object.

#### `GET /teams/{id}` — Retrieve a team

#### `PUT /teams/{id}` — Update a team

#### `DELETE /teams/{id}` — Remove a team

---

### Webhooks

Receive server-pushed events when task state changes (auto-assigned,
started, completed, failed).

#### `POST /webhooks` — Register a webhook URL

**Request:**

```json
{
  "url": "https://their-dashboard.example.com/webhooks/maidstech",
  "events": ["task.assigned", "task.started", "task.completed", "task.failed"],
  "secret": "whsec_<random>"
}
```

**Response (`201 Created`):**

```json
{ "id": "wh_01HB3...", "url": "https://...", "events": [...] }
```

MaidsTech signs each delivered event with HMAC-SHA256 using `secret`,
in the `X-MaidsTech-Signature` header.

#### Event payload example

```json
{
  "event": "task.assigned",
  "deliveredAt": "2026-04-21T17:30:05Z",
  "data": {
    "taskId": "2g4mQ6TKlaGSyHAA7NpVWPLs",
    "worker": "1LjhGUWdxFbvdsTdbyWb9Q~*",
    "state": "assigned",
    "estimatedArrivalTime": "2026-04-22T09:12:00Z"
  }
}
```

---

## Error format

All error responses share the same shape:

```json
{
  "code": "validation_error",
  "message": "teamId is required when autoAssign=true.",
  "details": { "field": "teamId" }
}
```

| HTTP | `code` | Meaning |
|---|---|---|
| 400 | `validation_error` | A request field is missing or malformed. |
| 401 | `unauthorized` | Missing or invalid API key. |
| 403 | `forbidden` | API key does not have access to the resource. |
| 404 | `not_found` | Task / worker / team does not exist. |
| 409 | `conflict` | Task state does not permit this action (e.g. deleting a completed task). |
| 422 | `unassignable` | Auto-assignment could not place the task (no eligible worker, all at capacity, etc.). |
| 429 | `rate_limited` | Too many requests; see `Retry-After` header. |
| 5xx | `internal_error` | MaidsTech issue; retry with exponential backoff. |

---

## Rate limits

- **Default:** 100 requests per minute per API key.
- **Batch endpoints** (`/tasks/batch`, `/tasks/reoptimize`) count as one
  request regardless of size.
- When throttled, the API returns `429` with a `Retry-After` header in
  seconds.

---

## Minimal quick start

```bash
curl -X POST https://api.maidstech.ai/v1/tasks \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "teamId": "wIFp5l~GOFVpGqV3yHyw6Gbl",
    "autoAssign": true,
    "destination": { "address": "123 Palm St, Jeddah" },
    "recipient": { "name": "Sara", "phone": "+966500000000" },
    "completeAfter": "2026-04-22T08:00:00Z",
    "completeBefore": "2026-04-22T12:00:00Z"
  }'
```

If the response has `"state": "assigned"` and a non-null `worker`,
auto-optimization worked. If it returns `"state": "unassigned"` with
`worker: null`, there is no eligible worker in the team for that time
window — register workers, put them on-duty, or widen the time window,
then call `POST /tasks/reoptimize` with the `taskIds`.

---

**Questions / access:** contact MaidsTech support.
