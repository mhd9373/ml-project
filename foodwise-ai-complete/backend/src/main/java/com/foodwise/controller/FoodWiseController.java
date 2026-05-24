package com.foodwise.controller;

import com.foodwise.model.*;
import com.foodwise.service.PredictionService;
import com.foodwise.service.AnalyticsService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.*;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
@CrossOrigin(origins = "${frontend.url:*}")
public class FoodWiseController {

    private final PredictionService predictionService;
    private final AnalyticsService analyticsService;

    // ─── Prediction ──────────────────────────────────────────────────────────

    /**
     * POST /api/v1/predict-demand
     * Calls the Python ML service and stores result in DB.
     */
    @PostMapping("/predict-demand")
    public ResponseEntity<PredictionResponse> predictDemand(
            @Valid @RequestBody PredictionRequest request) {
        PredictionResponse response = predictionService.predict(request);
        return ResponseEntity.ok(response);
    }

    /**
     * POST /api/v1/predict-demand/bulk
     * Bulk CSV prediction upload.
     */
    @PostMapping("/predict-demand/bulk")
    @PreAuthorize("hasAnyRole('ADMIN','MANAGER')")
    public ResponseEntity<BulkPredictionResponse> bulkPredict(
            @RequestParam("file") MultipartFile file) {
        BulkPredictionResponse response = predictionService.bulkPredict(file);
        return ResponseEntity.ok(response);
    }

    // ─── Analytics ───────────────────────────────────────────────────────────

    /**
     * GET /api/v1/analytics
     * Summary analytics for the dashboard.
     */
    @GetMapping("/analytics")
    public ResponseEntity<AnalyticsSummary> getAnalytics(
            @RequestParam(defaultValue = "7") int days,
            @RequestParam(required = false) String restaurant) {
        return ResponseEntity.ok(analyticsService.getSummary(days, restaurant));
    }

    /**
     * GET /api/v1/analytics/restaurants
     * Per-restaurant waste performance.
     */
    @GetMapping("/analytics/restaurants")
    public ResponseEntity<List<RestaurantAnalytics>> getRestaurantAnalytics(
            @RequestParam(defaultValue = "30") int days) {
        return ResponseEntity.ok(analyticsService.getRestaurantAnalytics(days));
    }

    /**
     * GET /api/v1/analytics/categories
     * Waste breakdown by food category.
     */
    @GetMapping("/analytics/categories")
    public ResponseEntity<List<CategoryAnalytics>> getCategoryAnalytics() {
        return ResponseEntity.ok(analyticsService.getCategoryAnalytics());
    }

    // ─── History ─────────────────────────────────────────────────────────────

    /**
     * GET /api/v1/history
     * Paginated prediction history.
     */
    @GetMapping("/history")
    public ResponseEntity<Page<PredictionRecord>> getHistory(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(required = false) String restaurant,
            @RequestParam(required = false) String riskLevel) {
        Pageable pageable = PageRequest.of(page, size, Sort.by("createdAt").descending());
        return ResponseEntity.ok(predictionService.getHistory(pageable, restaurant, riskLevel));
    }

    // ─── Export ──────────────────────────────────────────────────────────────

    @GetMapping("/export/csv")
    public ResponseEntity<byte[]> exportCsv(
            @RequestParam(defaultValue = "30") int days) {
        return analyticsService.exportCsv(days);
    }

    @GetMapping("/export/excel")
    @PreAuthorize("hasAnyRole('ADMIN','MANAGER')")
    public ResponseEntity<byte[]> exportExcel(
            @RequestParam(defaultValue = "30") int days) {
        return analyticsService.exportExcel(days);
    }

    // ─── ML Health ───────────────────────────────────────────────────────────

    @GetMapping("/ml/health")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Map<String, Object>> mlHealth() {
        return ResponseEntity.ok(predictionService.getMlHealth());
    }
}
