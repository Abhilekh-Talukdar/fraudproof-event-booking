// src/app/services/event.service.ts
import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError, tap } from 'rxjs/operators';
import { Event } from '../models/event.model';

// Define an interface for the booking payload
export interface BookingPayload {
    eventId: number;
    tickets: { name: string; dob: string }[];
}

// Define an interface for the booking response (adjust as needed based on backend)
export interface BookingResponse {
    success: boolean;
    message: string;
    bookingIds?: number[]; // Optional: backend might return generated IDs
}


@Injectable({
  providedIn: 'root'
})
export class EventService {
  private apiUrl = '/api'; // <-- NEW (CORS)

  constructor(private http: HttpClient) { }

  // --- Event Fetching (Should already be using HttpClient) ---
  getEvents(): Observable<Event[]> {
    console.log('EventService: fetching events from backend API');
    return this.http.get<Event[]>(`${this.apiUrl}/events`)
      .pipe(
        tap(events => console.log('Fetched events:', events)),
        catchError(this.handleError)
      );
  }

  getEventById(id: number): Observable<Event | undefined> {
    console.log(`EventService: fetching event with id=${id} from backend API`);
    return this.http.get<Event>(`${this.apiUrl}/events/${id}`)
      .pipe(
        tap(event => console.log(`Workspaceed event id=${id}:`, event)),
        catchError(this.handleError)
      );
  }

  // --- New Booking Method ---
  confirmBooking(bookingData: BookingPayload): Observable<BookingResponse> {
      console.log('EventService: sending booking confirmation to backend');
      return this.http.post<BookingResponse>(`${this.apiUrl}/bookings`, bookingData)
          .pipe(
              tap(response => console.log('Booking response from backend:', response)),
              catchError(this.handleError)
          );
  }

  // --- REMOVE OLD bookEvent method ---
  /*
  bookEvent(eventId: number, bookingDetails: any): Observable<any> { ... }
  */

  // --- Error Handling ---
  private handleError(error: HttpErrorResponse): Observable<never> {
    let errorMessage = 'An unknown error occurred!';
    // Default user-friendly message
    let userFriendlyMessage = 'An error occurred while processing your request. Please try again later.';

    // Check if running in a browser environment first before using ErrorEvent
    if (typeof ErrorEvent !== 'undefined' && error.error instanceof ErrorEvent) {
        // Client-side or network error (e.g., CORS preflight failure, network down)
        errorMessage = `Client Error/Network Error: ${error.message}`; // Use error.message
        userFriendlyMessage = `Could not reach the server. Please check your network connection. (${error.message})`;
    }
    // Check specifically for status 0, often indicating CORS or network issues before a server response
    else if (error.status === 0) {
        errorMessage = `Client Error/Network Error: Status 0 - Possibly CORS or Network issue. Message: ${error.message}`;
        userFriendlyMessage = `Could not connect to the server. Please check your network connection or contact support.`;
    }
    // Otherwise, assume it's a backend error response
    else {
        // Backend returned an unsuccessful response code.
        errorMessage = `Server Error: Status ${error.status}, Body: ${JSON.stringify(error.error)}`;
        // Try to get a more specific message from the backend response
        if (error.error && typeof error.error === 'object' && error.error.message) {
            userFriendlyMessage = `Server Error: ${error.error.message}`; // Use backend's message
        } else if (error.statusText) {
            userFriendlyMessage = `Server Error ${error.status}: ${error.statusText}`;
        } else {
            userFriendlyMessage = `An unexpected error occurred on the server (Status: ${error.status}).`;
        }
    }

    console.error('handleError details:', errorMessage); // Log detailed error for debugging
    // Return an observable with a user-facing error message wrapped in an Error object
    return throwError(() => new Error(userFriendlyMessage));
}
}