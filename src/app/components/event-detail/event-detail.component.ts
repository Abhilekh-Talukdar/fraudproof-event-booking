// src/app/components/event-detail/event-detail.component.ts
import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router'; // Import Router
import { EventService } from '../../services/event.service';
import { Event } from '../../models/event.model';
import { switchMap } from 'rxjs/operators';
import { Observable, of } from 'rxjs'; // Import 'of'

@Component({
  selector: 'app-event-detail',
  standalone: false,
  templateUrl: './event-detail.component.html',
  styleUrls: ['./event-detail.component.css']
})
export class EventDetailComponent implements OnInit {
  event$: Observable<Event | undefined> = of(undefined); // Initialize with an Observable
  bookingMessage: string | null = null;

  constructor(
    private route: ActivatedRoute,
    private router: Router, // Inject Router
    private eventService: EventService
  ) { }

  ngOnInit(): void {
    this.event$ = this.route.paramMap.pipe(
      switchMap(params => {
        const idParam = params.get('id');
        const eventId = idParam ? +idParam : 0; // Convert string 'id' to a number
        if (eventId > 0) {
          console.log(`EventDetailComponent: Fetching event with id=${eventId}`);
          return this.eventService.getEventById(eventId);
        } else {
          console.error('EventDetailComponent: Invalid event ID');
          // Handle invalid ID, maybe navigate back or show error
          return of(undefined); // Return an Observable of undefined
        }
      })
    );
  }

  // Simple booking simulation
  bookNow(eventId: number | undefined): void {
    if (eventId === undefined) {
      this.bookingMessage = "Cannot book: Event ID is missing.";
      return;
    }
    // In a real app, you might collect user details here
    const bookingDetails = { user: 'Test User', email: 'test@example.com' };

    this.eventService.bookEvent(eventId, bookingDetails).subscribe(response => {
      console.log('Booking response:', response);
      this.bookingMessage = response.success ? response.message : 'Booking failed (simulated).';
      // Optionally navigate away after booking
      // setTimeout(() => this.router.navigate(['/events']), 3000); // Go back to list after 3s
    }, error => {
      console.error('Booking error:', error);
      this.bookingMessage = 'An error occurred during booking (simulated).';
    });
  }

  goBack(): void {
    this.router.navigate(['/events']); // Navigate back to the event list
  }
}