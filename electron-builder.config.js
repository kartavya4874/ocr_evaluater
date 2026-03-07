/**
 * Electron Builder configuration
 */
module.exports = {
    appId: 'com.exameval.desktop',
    productName: 'Exam Evaluator',
    copyright: 'Copyright © 2024',

    directories: {
        output: 'build',
        buildResources: 'public',
    },

    files: [
        'dist/**/*',
        'electron/**/*',
        'package.json',
    ],

    extraResources: [
        {
            from: 'backend',
            to: 'backend',
            filter: [
                '**/*',
                '!__pycache__/**',
                '!*.pyc',
            ],
        },
    ],

    asar: true,
    asarUnpack: [
        'backend/**/*',
    ],

    win: {
        target: [
            {
                target: 'nsis',
                arch: ['x64'],
            },
        ],
        icon: 'public/icon.png',
    },

    nsis: {
        oneClick: false,
        allowToChangeInstallationDirectory: true,
        createDesktopShortcut: true,
        createStartMenuShortcut: true,
        shortcutName: 'Exam Evaluator',
    },

    mac: {
        target: [
            {
                target: 'dmg',
                arch: ['x64', 'arm64'],
            },
        ],
        icon: 'public/icon.png',
        category: 'public.app-category.education',
    },

    linux: {
        target: [
            {
                target: 'AppImage',
                arch: ['x64'],
            },
        ],
        icon: 'public/icon.png',
        category: 'Education',
    },
};
