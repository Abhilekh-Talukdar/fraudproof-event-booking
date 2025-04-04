import { Injectable } from '@angular/core';
import { Observable, of } from 'rxjs'; // 'of' creates an Observable from static data
import { Event } from '../models/event.model';

@Injectable({
  providedIn: 'root'
})
export class EventService {

  private hardcodedEvents: Event[] = [
    {
      id: 1,
      name: "Tech Innovators Conference",
      date: "2025-06-15",
      location: "Bangalore, Karnataka",
      description: "A gathering of tech leaders discussing the future of AI, blockchain, and software development.",
      price: 2999
    },
    {
      id: 2,
      name: "NH7 Weekender Music Festival",
      date: "2025-07-20",
      location: "Pune, Maharashtra",
      description: "India’s happiest music festival featuring top indie and international artists.",
      price: 2500
    },
    {
      id: 3,
      name: "Arijit Singh Live",
      date: "2025-09-10",
      location: "Mumbai, Maharashtra",
      description: "A soulful evening with Arijit Singh performing his greatest hits.",
      price: 3500
    },
    {
      id: 4,
      name: "Comic Con India",
      date: "2025-08-05",
      location: "Delhi",
      description: "A massive pop culture convention featuring comics, movies, video games, and celebrity panels.",
      price: 1500
    },
    {
      id: 5,
      name: "Sunburn Music Festival",
      date: "2025-10-12",
      location: "Goa",
      description: "Asia’s biggest electronic music festival with top DJs from around the world.",
      price: 4000
    },
    {
      id: 6,
      name: "India Food & Wine Festival",
      date: "2025-11-03",
      location: "Jaipur, Rajasthan",
      description: "A celebration of India's rich culinary heritage with global influences.",
      price: 1800
    },
    {
      id: 7,
      name: "Shreya Ghoshal Live",
      date: "2025-08-25",
      location: "Hyderabad, Telangana",
      description: "A mesmerizing night with the queen of Indian playback singing.",
      price: 2800
    },
    {
      id: 8,
      name: "Christmas Carnival",
      date: "2025-12-25",
      location: "Kolkata, West Bengal",
      description: "A festive celebration with music, food, and holiday cheer at Park Street.",
      price: 1000
    }
  ];

  constructor() { }

  getEvents(): Observable<Event[]> {
    console.log('EventService: fetching hardcoded events');
    // 'of' simulates an HTTP response with the hardcoded data
    return of(this.hardcodedEvents);
  }

  // Method to get a single event by ID (returns an Observable)
  getEventById(id: number): Observable<Event | undefined> {
    console.log(`EventService: fetching event with id=${id}`);
    const event = this.hardcodedEvents.find(e => e.id === id);
    return of(event); // Returns Observable<Event> or Observable<undefined>
  }

  // Placeholder for booking logic (will interact with backend later)
  bookEvent(eventId: number, bookingDetails: any): Observable<any> {
    console.log(`Booking event ${eventId} with details:`, bookingDetails);
    // In a real app, this would make an HTTP POST request
    // For now, just return a success simulation
    return of({ success: true, message: `Event ${eventId} booked (simulated).` });
  }
}
