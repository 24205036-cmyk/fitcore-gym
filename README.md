# FITCORE — Smart Gym Management & Real-Time Occupancy System

> A production-ready full-stack Gym Management System built with **Python 3, Flask, PyMongo, MongoDB Atlas, Bootstrap 5, and Vanilla JavaScript**.

FITCORE is designed for commercial fitness clubs, gym administrators, trainers, and front-desk staff to manage members, trainers, memberships, attendance, workouts, payments, notifications, and real-time gym occupancy from a single web application.

---

## 🌟 Key Features

### 1. 🟢 Real-Time Gym Occupancy & Traffic Density

- Live occupancy counter showing members currently inside the gym.
- Example: `47 / 100`.
- Dynamic CSS progress gauge.
- Occupancy status levels:
  - 🟢 Normal — 0% to 50%
  - 🟡 Moderately Busy — 51% to 80%
  - 🟠 Crowded — 81% to 99%
  - 🔴 Full — 100%
- Hard capacity protection prevents check-in when maximum capacity is reached.
- Backend validation also prevents capacity overflow.
- Hourly occupancy information calculated from attendance records.
- Vanilla JavaScript polling refreshes live occupancy information without a full-page reload.
- No Chart.js, canvas charts, or graph libraries are required.

---

## 2. 👥 Complete Member Management

FITCORE provides complete member management functionality.

### Member Features

- Add members
- View member details
- Edit member information
- Search members
- Filter members
- Deactivate members
- Renew memberships
- View membership status
- View attendance history
- View payment history
- Assign trainers
- Profile photo upload

### Member IDs

Members receive sequential IDs such as:

```text
GYM001
GYM002
GYM003
GYM004