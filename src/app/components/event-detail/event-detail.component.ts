// src/app/components/event-detail/event-detail.component.ts
import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router'; // Import Router
import { EventService } from '../../services/event.service';
import { Event } from '../../models/event.model';
import { switchMap } from 'rxjs/operators';
import { Observable, of } from 'rxjs';

@Component({
  selector: 'app-event-detail',
  standalone: false,
  templateUrl: './event-detail.component.html',
  styleUrls: ['./event-detail.component.css']
})
export class EventDetailComponent implements OnInit {
  event$: Observable<Event | undefined> = of(undefined);
  // bookingMessage: string | null = null; // REMOVE

  constructor(
    private route: ActivatedRoute,
    private router: Router, // Inject Router
    private eventService: EventService
  ) { }

  ngOnInit(): void {
    // Keep this logic to fetch event details
    this.event$ = this.route.paramMap.pipe(
      switchMap(params => {
        const idParam = params.get('id');
        const eventId = idParam ? +idParam : 0;
        if (eventId > 0) {
          return this.eventService.getEventById(eventId);
        } else {
          this.router.navigate(['/events']); // Redirect if ID is invalid
          return of(undefined);
        }
      })
    );
  }

  // Method to navigate to the booking form
  navigateToBooking(eventId: number | undefined): void {
    if (eventId !== undefined) {
      this.router.navigate(['/events', eventId, 'book']);
    } else {
        console.error("Cannot navigate to booking: Event ID is missing.");
        // Optionally show an error message to the user
    }
  }

  goBack(): void {
    this.router.navigate(['/events']);
  }

   // REMOVE the old bookNow method
   /*
   bookNow(eventId: number | undefined): void { ... }
   */
}