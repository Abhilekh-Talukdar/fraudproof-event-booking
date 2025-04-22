# Fraudproof Event Booking Application

A web application for browsing upcoming events and booking tickets. Built with an Angular frontend (utilizing Server-Side Rendering - SSR) and a Python Flask backend, using SQLite for simple data storage.

```mermaid
graph TD
    subgraph Event Booking System
        P1["1.0 Serve Frontend App<br>(Nginx + Node SSR)"];
        P2["2.0 Manage Event Data<br>(Flask API)"];
        P3["3.0 Handle Bookings<br>(Flask API)"];
    end

    User((User)) -- Event Page Request --> P1;
    P1 -- Display Events/Forms --> User;

    P1 -- Request Event List/Details --> P2;
    P2 -- Return Event List/Details --> P1;

    P1 -- Submit Booking Data --> P3;
    P3 -- Return Booking Confirmation/Error --> P1;

    P2 -- Read Events --> DS1[(Events DB)];
    P3 -- Read Event Info --> DS1;
    P3 -- Write Booking --> DS2[(Bookings DB)];

    classDef external fill:#f9f,stroke:#333,stroke-width:2px,color:#000;
    classDef process fill:#ccf,stroke:#333,stroke-width:2px,color:#000;
    classDef datastore fill:#ffc,stroke:#333,stroke-width:2px,shape:,color:#000;
    class User external;
    class P1,P2,P3 process;
    class DS1,DS2 datastore;
```

## Features

* View a list of available events fetched from the backend API.
* See detailed information for each event.
* Book 1 to 4 tickets for an event.
* Enter Name and Date of Birth for each ticket being booked.
* Booking details are stored in the backend database.

## Technologies Used

* **Frontend:** Angular (~17/18+), TypeScript, HTML, CSS
* **Backend:** Python 3, Flask
* **Database:** SQLite 3
* **API Communication:** RESTful API, CORS (for local development)
* **Node.js/npm:** For Angular development and building
* **Python Virtual Environment (`venv`):** For backend dependency management
* **(Deployment):** Gunicorn (WSGI Server), Nginx (Reverse Proxy), Systemd (Process Management), Angular SSR Node Server, Linux (GCP)
