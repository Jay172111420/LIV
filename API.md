# API

Base path `/api`. JSON in, JSON out. Interactive docs at `/api/docs` while the server runs.
Everything except `register`, `login`, `logout` and `health` requires the session cookie set at login.

## Errors

```json
{ "error": { "code": "validation_error", "message": "Some of the information you entered isn't valid.",
             "details": [ { "field": "age", "message": "Input should be greater than or equal to 13" } ] } }
```

| Status | Meaning | Example codes |
| --- | --- | --- |
| 400 | Valid shape, invalid reference | `invalid_goal`, `invalid_equipment`, `invalid_exercise`, `duplicate_exercise` |
| 401 | Not logged in / bad credentials | `not_authenticated`, `invalid_credentials` |
| 403 | Cross-origin write blocked | `forbidden_origin` |
| 404 | Not found, or belongs to someone else | `not_found` |
| 409 | Conflict | `email_taken` |
| 422 | Validation failed | `validation_error` |
| 500 | Server or database problem | `internal_error`, `database_error` |

## Endpoints

### Auth
| Method | Path | Notes |
| --- | --- | --- |
| POST | `/auth/register` | `{email, password}` (10 to 128 chars). Creates the account, empty profile, sets cookie. 201 |
| POST | `/auth/login` | `{email, password}`. Sets cookie |
| POST | `/auth/logout` | Ends the session server-side. 204 |
| GET | `/auth/me` | Current user |

### Profile
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/profile` | Includes `goal`, `equipment`, `preferred_training_days`, `onboarding_complete` |
| PUT | `/profile` | Partial update: only sent fields change, `null` clears. `equipment_ids` and `preferred_training_days` replace the whole list |

### Reference data
| Method | Path |
| --- | --- |
| GET | `/goals` |
| GET | `/equipment` |
| GET | `/exercises/muscle-groups` |

### Exercises
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/exercises` | Query: `q`, `muscle_group_id`, `equipment_id`, `limit` (1-100), `offset`. Built-in plus your own |
| POST | `/exercises` | Creates a private custom exercise. 201 |
| GET | `/exercises/{id}` | |

### Workouts
| Method | Path | Notes |
| --- | --- | --- |
| GET, POST | `/workouts` | Workout plans |
| GET | `/workouts/{id}` | |
| GET, POST | `/workout-sessions` | POST accepts nested `exercises[].sets[]`. `set_number` and `position` are assigned by order |
| GET | `/workout-sessions/{id}` | |

### Body metrics
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/body-metrics` | Query: `metric_type`, `limit` (1-200), `offset`. Newest first |
| POST | `/body-metrics` | Values in kg / cm / %. `custom` needs `custom_label` and `unit` |
| DELETE | `/body-metrics/{id}` | 204 |

### Nutrition
| Method | Path | Notes |
| --- | --- | --- |
| GET, PUT | `/nutrition/profile` | Targets, `dietary_preference`, `allergies`, `restrictions`. Partial update like `/profile` |

### Meta
`GET /health` returns `{"status": "ok"}`.

## Not yet implemented

Updating or deleting workout plans and sessions, editing or deleting custom exercises, password change,
account deletion. They aren't needed for Phase 0.
