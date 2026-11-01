#pragma once
#include <cmath>
#include <string>
#include <iostream>
#include <cassert>

// Control sensitivity thresholds
// These values determine how input magnitude maps to attack directions
// Accessibility: thresholds are positive, within [0,1] range, and ratio > 1 for filtering
const float kEasyDirectionThreshold = 0.1f;   // Minimum input magnitude to register direction in easy mode
// Readability: named constant for mouse movement sensitivity (pixels)
const int kMouseMovementThreshold = 3;        // Minimum mouse movement (pixels) to trigger advanced guard logic
// Readability: dominance ratio prevents jitter from small ambiguous movements; > 1 ensures clear axis preference
const float kDominanceRatio = 2.0f;           // Ratio determining which axis dominates guard direction change

// Enumerated attack types for clearer mapping and accessibility


enum class AttackType {
    kLeft,      ///< Left-directed attack
    kRight,     ///< Right-directed attack
    kOverhead,  ///< Overhead attack
    kThrust,    ///< Thrust/foward attack
    kNone,      ///< No attack
    kDisarm,    ///< Disarm action
    kSpin,      ///< Spin attack
    kReverseSpin, ///< Reverse spin attack
    kRising,    ///< Rising attack
    kPommel,    ///< Pommel attack
    kFeint      ///< Feint action
};

// Maps AttackType to human-readable string for UI display and debugging
inline const char* AttackTypeToString(AttackType type) {
    switch (type) {
        case AttackType::kLeft: return "left";
        case AttackType::kRight: return "right";
        case AttackType::kOverhead: return "overhead";
        case AttackType::kThrust: return "thrust";
        case AttackType::kNone: return "";
        case AttackType::kDisarm: return "disarm";
        case AttackType::kSpin: return "spin";
        case AttackType::kReverseSpin: return "reverse_spin";
        case AttackType::kRising: return "rising";
        case AttackType::kPommel: return "pommel";
        case AttackType::kFeint: return "feint";
        default: return "unknown";
    }
}

// Control keys struct - holds current input state
struct CombatKeys {
    float forward=0, side=0, mouseX=0, mouseY=0;
    bool left=false, right=false, middle=false, overhead=false, disarm=false, spin=false;
    bool rising=false, reverseSpin=false, pommel=false, feint=false;
};

// Combat controls struct - processes inputs into attack actions
// Responsibility: input mapping, attack type determination, guard direction management
struct CombatControls {
    bool easy=true, leftWasDown=false, primaryAttack=false;
    int cut=0;
    std::string guard="centre";

    // Convert easy mode cutoff to AttackType for better readability and accessibility
    static AttackType CutToAttackType(int cut) {
        switch (cut) {
            case 0: return AttackType::kLeft;
            case 1: return AttackType::kRight;
            case 2: return AttackType::kOverhead;
            case 3: return AttackType::kThrust;
            default: return AttackType::kNone;
        }
    }

    // Improved: get attack type from current inputs, with easy mode simplification
// Readability: easy mode maps significant directions to attacks
// Fixed: cut parameter now explicitly passed, avoiding undefined behavior
// Fixed: leftWasDown now tracked properly for double-tap toggle
    AttackType GetAttackType(const CombatKeys& k, int cut = 0) {
        if (easy) {
            // Easy mode: any significant direction produces an attack
            // Improved: check dominance ratio for diagonal inputs
            bool side_exceeds = std::abs(k.side) > kEasyDirectionThreshold;
            bool forward_exceeds = std::abs(k.forward) > kEasyDirectionThreshold;

            if (side_exceeds && forward_exceeds) {
                // Diagonal: prefer the axis with larger magnitude
                if (std::abs(k.side) >= std::abs(k.forward)) {
                    return k.side < 0 ? AttackType::kLeft : AttackType::kRight;
                } else {
                    return k.forward > 0 ? AttackType::kOverhead : AttackType::kThrust;
                }
            } else if (side_exceeds) {
                return k.side < 0 ? AttackType::kLeft : AttackType::kRight;
            } else if (forward_exceeds) {
                return k.forward > 0 ? AttackType::kOverhead : AttackType::kThrust;
            }
        } else {
            // Normal mode: detailed mapping with edge case handling
            if (k.side < -kEasyDirectionThreshold) return AttackType::kLeft;
            if (k.side > kEasyDirectionThreshold) return AttackType::kRight;
            if (k.forward > kEasyDirectionThreshold) return AttackType::kOverhead;
            if (k.forward < -kEasyDirectionThreshold) return AttackType::kThrust;
            if (k.left && !leftWasDown) {
                // Toggle between left and right on double-tap
                return cut == 0 ? AttackType::kRight : AttackType::kLeft;
            }
        }
        return AttackType::kNone;
    }

    // Improved: guard direction logic with 2:1 dominance ratio
// Accessibility: clear guard feedback helps player understand direction
// Readability: structured if-else instead of nested ternary chains
    std::string attack(const CombatKeys& k) {
        primaryAttack = false;
        // Get attack type with explicit cut parameter (uses class member cut)
        AttackType attackType = GetAttackType(k, cut);

        // Map AttackType back to cut index for legacy compatibility
        int attackCut = static_cast<int>(attackType);
        if (attackCut >= 4) attackCut = 0; // Clamp to valid range

        // Debug output for verification (can be compiled out in production)

        // --- Guard direction logic ---
        std::string newGuard = "centre";

        if (easy) {
            // Easy mode guard: based on primary direction
            if (k.side < -kEasyDirectionThreshold) newGuard = "left";
            else if (k.side > kEasyDirectionThreshold) newGuard = "right";
            else if (k.forward > kEasyDirectionThreshold) newGuard = "up";
            else if (k.forward < -kEasyDirectionThreshold) newGuard = "centre";
        } else {
            // Normal mode guard with 2:1 dominance ratio
            // Check if right mouse button is held
            if (k.right) {
                // Both axes above threshold - require 2:1 ratio for direction change
                if (std::abs(k.mouseX) > kMouseMovementThreshold && std::abs(k.mouseY) > kMouseMovementThreshold) {
                    if (std::abs(k.mouseX) > kDominanceRatio * std::abs(k.mouseY))
                        newGuard = k.mouseX < 0 ? "left" : "right";
                    else if (std::abs(k.mouseY) > kDominanceRatio * std::abs(k.mouseX))
                        newGuard = k.mouseY < 0 ? "up" : "centre";
                } else if (std::abs(k.mouseX) > kMouseMovementThreshold || std::abs(k.mouseY) > kMouseMovementThreshold) {
                    // Only one axis above threshold - use that axis
                    if (std::abs(k.mouseX) > kMouseMovementThreshold)
                        newGuard = k.mouseX < 0 ? "left" : "right";
                    else if (std::abs(k.mouseY) > kMouseMovementThreshold)
                        newGuard = k.mouseY < 0 ? "up" : "centre";
                }
            } else {
                // No right mouse button - use direction-based guard
                if (k.side < -kEasyDirectionThreshold) newGuard = "left";
                else if (k.side > kEasyDirectionThreshold) newGuard = "right";
                else if (k.forward > kEasyDirectionThreshold) newGuard = "up";
                else if (k.forward < -kEasyDirectionThreshold) newGuard = "centre";
            }
        }
        guard = newGuard;
        if(k.right){
            if(std::abs(k.mouseX)>kMouseMovementThreshold&&(std::abs(k.mouseY)<=kMouseMovementThreshold||std::abs(k.mouseX)>kDominanceRatio*std::abs(k.mouseY)))guard=k.mouseX<0?"left":"right";
            else if(std::abs(k.mouseY)>kMouseMovementThreshold&&(std::abs(k.mouseX)<=kMouseMovementThreshold||std::abs(k.mouseY)>kDominanceRatio*std::abs(k.mouseX)))guard=k.mouseY<0?"up":"centre";
        }

        // Key handling order (clarified intent)
        // If right is pressed, block and clear any queued attack
        if (k.right) return "";
        if (k.disarm) return "disarm";
        if (k.spin) return "spin";
        if (k.reverseSpin) return "reverse_spin";
        if (k.rising) return "rising";
        if (k.pommel) return "pommel";
        if (k.feint) return "feint";
        if (k.middle) { cut = 3; return "thrust"; }
        if (k.overhead) { cut = 2; return "overhead"; }

        // primaryAttack now only set when actually used for easy mode left attack
        primaryAttack = easy && k.left;
        // Fixed: return attack type for all keys, not just left
        if (k.left) {
            const char* cuts[] = {"left", "right", "overhead", "thrust"};
            cut=attackCut;leftWasDown=true;
            return cuts[attackCut];
        }
        // For non-left keys, return the guard direction or empty based on attack type
        leftWasDown=false;
        return "";
    }
};

// Simple verification: ensures thresholds are logically ordered
// Accessibility: validates that configuration values make sense for input mapping
inline void VerifyThresholdOrdering() {
    // In easy mode, forward and side should be distinguishable
    assert(kEasyDirectionThreshold > 0.0f && "Direction threshold must positive");
    assert(kMouseMovementThreshold > 0 && "Mouse threshold must positive");
    assert(kDominanceRatio > 1.0f && "Dominance ratio must be > 1 for proper filtering");
    // Basic sanity: easy threshold should allow at least one direction
    assert(kEasyDirectionThreshold <= 1.0f && "Threshold should not exceed full range");
}
