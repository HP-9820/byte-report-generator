import React, { useEffect, useRef } from 'react';
import gsap from 'gsap';

const CustomCursor = () => {
    const cursorRef = useRef(null);
    const followerRef = useRef(null);

    useEffect(() => {
        const moveCursor = (e) => {
            gsap.to(cursorRef.current, {
                x: e.clientX,
                y: e.clientY,
                duration: 0.1,
            });
            gsap.to(followerRef.current, {
                x: e.clientX,
                y: e.clientY,
                duration: 0.3,
            });
        };

        window.addEventListener('mousemove', moveCursor);
        return () => window.removeEventListener('mousemove', moveCursor);
    }, []);

    return (
        <>
            <div ref={cursorRef} className="fixed top-0 left-0 w-2 h-2 bg-white rounded-full pointer-events-none z-[9999] mix-blend-difference transform -translate-x-1/2 -translate-y-1/2" />
            <div ref={followerRef} className="fixed top-0 left-0 w-10 h-10 border border-white/20 rounded-full pointer-events-none z-[9998] transform -translate-x-1/2 -translate-y-1/2" />
        </>
    );
};

export default CustomCursor;
