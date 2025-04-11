// src/app/components/booking-form/booking-form.component.ts
import { Component, OnInit, OnDestroy } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { FormBuilder, FormGroup, FormArray, Validators } from '@angular/forms';
import { EventService } from '../../services/event.service';
import { Event } from '../../models/event.model';
import { Subscription, Observable, of } from 'rxjs';
import { switchMap, take } from 'rxjs/operators';

@Component({
  selector: 'app-booking-form',
  standalone: false,
  templateUrl: './booking-form.component.html',
  styleUrls: ['./booking-form.component.css']
})
export class BookingFormComponent implements OnInit, OnDestroy {
  event$: Observable<Event | undefined> = of(undefined);
  bookingForm: FormGroup;
  eventId: number = 0;
  isLoading = false;
  errorMessage: string | null = null;
  successMessage: string | null = null;
  maxTickets = 4; // Max tickets allowed
  numberOfTicketsOptions = Array.from({ length: this.maxTickets }, (_, i) => i + 1); // [1, 2, 3, 4]

  private routeSub: Subscription | undefined;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private fb: FormBuilder,
    private eventService: EventService
  ) {
    // Initialize the main form group
    this.bookingForm = this.fb.group({
      numberOfTickets: [1, [Validators.required, Validators.min(1), Validators.max(this.maxTickets)]],
      tickets: this.fb.array([]) // Initialize as empty FormArray
    });
  }

  ngOnInit(): void {
    this.isLoading = true;
    this.routeSub = this.route.paramMap.pipe(
      switchMap(params => {
        const idParam = params.get('id');
        this.eventId = idParam ? +idParam : 0;
        if (this.eventId > 0) {
          this.event$ = this.eventService.getEventById(this.eventId);
          return this.event$; // Pass the observable down
        } else {
          this.errorMessage = 'Invalid Event ID.';
          this.router.navigate(['/events']);
          return of(undefined); // Return empty observable
        }
      }),
      take(1) // Take only the first emission
    ).subscribe({
      next: (event) => {
        if (!event) {
          this.errorMessage = 'Event not found.';
          this.router.navigate(['/events']);
        } else {
            // Event loaded, update the form based on initial numberOfTickets
            this.updateTicketForms(this.bookingForm.get('numberOfTickets')?.value);
        }
        this.isLoading = false;
      },
      error: (err) => {
        this.errorMessage = `Error loading event details: ${err.message || 'Unknown error'}`;
        console.error(err);
        this.isLoading = false;
      }
    });

    // Subscribe to changes in the numberOfTickets control
    this.bookingForm.get('numberOfTickets')?.valueChanges.subscribe(num => {
       if (num >= 1 && num <= this.maxTickets) {
         this.updateTicketForms(num);
       }
    });
  }

  // Helper getter for easy access to the tickets FormArray in the template
  get ticketsFormArray(): FormArray {
    return this.bookingForm.get('tickets') as FormArray;
  }

  // Dynamically add/remove ticket forms based on selection
  updateTicketForms(numTickets: number): void {
      const currentTickets = this.ticketsFormArray.length;

      if (numTickets > currentTickets) {
          // Add new forms
          for (let i = currentTickets; i < numTickets; i++) {
              this.ticketsFormArray.push(this.createTicketForm());
          }
      } else if (numTickets < currentTickets) {
          // Remove excess forms
          for (let i = currentTickets; i > numTickets; i--) {
              this.ticketsFormArray.removeAt(i - 1);
          }
      }
       // Ensure the first form is created if numTickets is 1 and array is empty
      if (numTickets === 1 && this.ticketsFormArray.length === 0) {
          this.ticketsFormArray.push(this.createTicketForm());
      }
  }

  // Create a FormGroup for a single ticket
  createTicketForm(): FormGroup {
    return this.fb.group({
      name: ['', Validators.required],
      dob: ['', Validators.required] // Date of Birth
    });
  }

  onSubmit(): void {
    this.errorMessage = null;
    this.successMessage = null;

    if (this.bookingForm.invalid) {
        this.errorMessage = 'Please fill in all required fields for each ticket.';
        // Mark all fields as touched to show validation errors
        this.bookingForm.markAllAsTouched();
        return;
    }

    this.isLoading = true;
    const bookingData = {
      eventId: this.eventId,
      tickets: this.ticketsFormArray.value // Get the array of ticket details
    };

    console.log('Submitting booking data:', bookingData);

    this.eventService.confirmBooking(bookingData).subscribe({
      next: (response) => {
        console.log('Booking successful:', response);
        this.isLoading = false;
        this.successMessage = response.message || 'Booking successful!';
        // Optionally clear form or disable it
        this.bookingForm.reset({ numberOfTickets: 1 }); // Reset form
        this.ticketsFormArray.clear(); // Clear the dynamic array
        this.updateTicketForms(1); // Re-add one form group
        // Optionally navigate away after a delay
         setTimeout(() => this.router.navigate(['/events']), 5000); // Go back to list after 5s
      },
      error: (err) => {
        console.error('Booking failed:', err);
        this.isLoading = false;
        this.errorMessage = `Booking failed: ${err.message || 'Please try again.'}`;
      }
    });
  }

   goBack(): void {
      // Navigate back to the event detail page
      this.router.navigate(['/events', this.eventId]);
   }

  ngOnDestroy(): void {
    if (this.routeSub) {
      this.routeSub.unsubscribe();
    }
  }
}