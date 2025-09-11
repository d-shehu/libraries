import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ApiView } from './api-view';

describe('ApiView', () => {
  let component: ApiView;
  let fixture: ComponentFixture<ApiView>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ApiView]
    })
    .compileComponents();

    fixture = TestBed.createComponent(ApiView);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
