import { FormBuilder } from '@angular/forms';
import { Router } from '@angular/router';
import { of } from 'rxjs';

import { AuthService } from '../../services/auth.service';
import { LoginComponent } from './login.component';

describe('LoginComponent password validation', () => {
  let component: LoginComponent;

  beforeEach(() => {
    const auth = {
      login: jasmine.createSpy('login').and.returnValue(of({ user: null })),
      register: jasmine.createSpy('register').and.returnValue(of({ user: null }))
    } as unknown as AuthService;
    const router = {
      navigate: jasmine.createSpy('navigate').and.returnValue(Promise.resolve(true))
    } as unknown as Router;

    component = new LoginComponent(new FormBuilder(), auth, router);
  });

  it('allows a short existing password in sign-in mode', () => {
    component.form.setValue({ email: 'user@example.test', password: 'short' });

    expect(component.isRegistering).toBeFalse();
    expect(component.form.valid).toBeTrue();
  });

  it('enforces the 12-character minimum in registration mode', () => {
    component.form.setValue({ email: 'user@example.test', password: 'short' });
    component.setRegistrationMode(true);

    expect(component.form.get('password')?.hasError('minlength')).toBeTrue();
    expect(component.form.invalid).toBeTrue();

    component.form.get('password')?.setValue('long-enough-password');
    expect(component.form.valid).toBeTrue();
  });

  it('removes the registration-only minimum when switching back to sign-in', () => {
    component.setRegistrationMode(true);
    component.form.setValue({ email: 'user@example.test', password: 'short' });
    expect(component.form.invalid).toBeTrue();

    component.setRegistrationMode(false);

    expect(component.form.valid).toBeTrue();
    expect(component.form.get('password')?.hasError('minlength')).toBeFalse();
  });
});
