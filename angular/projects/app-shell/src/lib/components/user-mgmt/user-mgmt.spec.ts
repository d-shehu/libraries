import { ComponentFixture, TestBed } from '@angular/core/testing';

import { UserMgmt } from './user-mgmt';

describe('UserMgmt', () => {
  let component: UserMgmt;
  let fixture: ComponentFixture<UserMgmt>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [UserMgmt]
    })
    .compileComponents();

    fixture = TestBed.createComponent(UserMgmt);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
