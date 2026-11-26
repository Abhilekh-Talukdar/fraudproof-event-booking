import { Component } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-login',
  standalone: false,
  templateUrl: './login.component.html',
  styleUrl: './login.component.css'
})
export class LoginComponent {
  isRegistering = false;
  isLoading = false;
  errorMessage: string | null = null;
  form: FormGroup;

  constructor(private fb: FormBuilder, private auth: AuthService, private router: Router) {
    this.form = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
      // Existing accounts should be able to sign in regardless of the current
      // registration password policy.
      password: ['', [Validators.required]]
    });
  }

  setRegistrationMode(registering: boolean): void {
    this.isRegistering = registering;
    const password = this.form.get('password');
    if (!password) {
      return;
    }

    password.setValidators(
      registering
        ? [Validators.required, Validators.minLength(12)]
        : [Validators.required]
    );
    password.updateValueAndValidity();
    this.errorMessage = null;
  }

  submit(): void {
    this.errorMessage = null;
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.isLoading = true;
    const { email, password } = this.form.getRawValue();
    const action = this.isRegistering
      ? this.auth.register(email!, password!)
      : this.auth.login(email!, password!);
    action.subscribe({
      next: () => {
        this.isLoading = false;
        this.router.navigate(['/events']);
      },
      error: error => {
        this.isLoading = false;
        this.errorMessage = error.error?.message || error.error?.error || 'Authentication failed.';
      }
    });
  }
}
